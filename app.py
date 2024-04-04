from io import BytesIO
import json
import plotly.graph_objects as go
import pandas as pd

from viktor import ViktorController
from viktor.parametrization import ViktorParametrization, OutputField, NumberField, OptionField, LineBreak, \
    Text, Step, Lookup, Section, OptionField, BooleanField, TextAreaField
from viktor.external.generic import GenericAnalysis
from viktor.views import GeometryView, PDFView
from viktor.views import GeometryResult
from viktor.views import MapPolygon, MapPoint, MapResult, MapView
from viktor.views import PlotlyView, PlotlyResult
from viktor.views import DataGroup, DataItem, DataResult, DataView
from viktor import File
from viktor.views import PDFView, PDFResult

import inferenceEngine

DEFAULT_EHR = 101020350  # Akadeemia tee 4, 101027657 Estonia Teater

vslist = inferenceEngine.get_kb_excel_sheet('vs')['Nimetus'].tolist()
kllist = inferenceEngine.get_kb_excel_sheet('katus')['Nimetus'].tolist()
slist = inferenceEngine.get_kb_excel_sheet('sokkel')['Nimetus'].tolist()
ohulekelist = inferenceEngine.get_kb_excel_sheet('õhuleke')['Nimetus'].tolist()

ksyslist = inferenceEngine.get_kb_excel_sheet('küttesüsteem')['Nimetus'].tolist()
kjaotuslist = inferenceEngine.get_kb_excel_sheet('soojusjaotus')['Nimetus'].tolist()
ventlist = inferenceEngine.get_kb_excel_sheet('ventilatsioon')['Nimetus'].tolist()


class Parametrization(ViktorParametrization):
    """Kõik sisendväärtused, etapilisus ja väljundaknad tulevad selle klassi parameetritest."""

    """Esimene etapp on konkreetse renoveeritava hoone määramine."""
    et_intr = Step('Vali hoone', views=['get_map_view'], previous_label='...', next_label='Edasi')
    et_intr.intro = Text(
        '# Renokratt \n '
        'Renokratt on tark abiline korterelamute renoveerimise lähteülesande loomiseks. \n\n'
        'Renokrati eesmärk on vähendada renoveerimisprotsessi tegelikku '
        'ja tunnetatud keerukust ning leevendada renoveerimisega seotud väärarusaami. '
        'Renokratt võimaldab Sul leida just Sinu hoonele kõige sobivama renoveerimislahenduse '
        'ning aitab Sul luua võimalikult konkreetse ja kvaliteetse lähteülesande projekteerijale ja ehitajale. \n\n'
        'Alustamiseks sisesta vaid oma hoone Ehitusregistri kood (selle leiad aadressilt ehr.ee) '
        'ja seejärel vajuta alumises paremas nurgas "Edasi" nupule.')
    et_intr.ehr = NumberField('EHR kood', default=DEFAULT_EHR, flex=100)
    et_intr.lb1 = LineBreak()
    et_intr.tyyp = OutputField('Hoone tüüp:', value=inferenceEngine.app_get_typo_kood, flex=100)
    et_intr.selgitus = Text("Käesolev abiline on välja töötatud enne 2000ndat aastat ehitatud telliskivist, "
                            "plokkidest ja raudbetoonpaneelidest korterelamutele. \n"
                            "Juhul kui valitud hoone tüüp ei ole teada, siis võib programmis esineda vigu.")
    et_intr.lb2 = LineBreak()
    et_intr.credits = Text("Prototüüp on välja töötatud magistritöö raames.\n\n"
                           "Autor: Joosep Viik\n\n"
                           "Tallinna Tehnikaülikool\n\n"
                           "2024")
    et_intr.laiskadele = Text("1-464 paneelmaja: 101020350 \n\n"
                              "Tartu paneelmaja: 104018667 \n\n "
                              "Tallinna paneelmaja: 101010705 \n\n "
                              "Põlva kivimaja: 110009871 \n\n"
                              "Teadmata tüübiga hoone: 101027657")

    """Teine etapp on tänase olukorra täpsustamine ja EhR andmete parandamine."""
    et_par = Step('Kontrolli', views=['run_grasshopper', 'visualize_data'],
                  previous_label='Tagasi', next_label='Edasi')
    et_par.sec_intro = Section('Sissejuhatus')
    et_par.sec_intro.intro = Text('## Lähteandmete täpsustamine \n'
                                  'Sinu valitud hoone kohta on olemas palju avaandmeid, kuid need andmed on '
                                  'puudulikud ja ka olemasolevad andmed pole tihti usaldusväärsed. \n\n'
                                  'Siin lehel saad Sa oma hoone kohta käivaid andmeid täpsustada '
                                  'ja ka tänast hoone olukorda paremini kirjeldada.')
    et_par.sec_olol = Section('Eelnevalt teostatud tööd')
    et_par.sec_olol.katkate = BooleanField('Kas katusekate on vahetatud?', flex=100)
    et_par.sec_olol.katsooj = BooleanField('Kas katuslage või pööningut on täiendavalt soojustatud?', flex=100)
    et_par.sec_olol.vssooj = OptionField('Kas välisseinasid on soojustatud?',
                                         options=['Ei', 'Otsaseinad', 'Terve hoone'], flex=100)
    et_par.sec_olol.soksooj = BooleanField('Kas soklit on soojustatud?', flex=100)
    et_par.sec_olol.silriba = BooleanField('Kas sillutisriba on uuendatud?', flex=100)
    et_par.sec_olol.sooj = NumberField('Kui suur osa akendest on vahetatud? (ligikaudne vahetuse %)', variant='slider',
                                       min=0, max=100, flex=100)
    et_par.sec_olol.kytsys = BooleanField('Kas küttesüsteem on rekonstrueeritud?', flex=100)
    et_par.sec_olol.veetor = BooleanField('Kas veetorustik on vahetatud?', flex=100)
    et_par.sec_olol.kantor = BooleanField('Kas kanalisatsioonitorustik on vahetatud?', flex=100)
    et_par.sec_olol.elsys = BooleanField('Kas elektrisüsteem on uuendatud?', flex=100)
    et_par.sec_olol.toltokestus = BooleanField('Kas on teostatud tuletõkestustöid?', flex=100)
    et_par.sec_olol.markused = TextAreaField('Lisamärkused', flex=100)

    et_par.sec_ehr = Section('EhR andmete korrigeerimine')
    et_par.sec_ehr.raj_a = OutputField('Hoone rajamise aasta:', value="", flex=100)
    et_par.sec_ehr.koepin = OutputField('Köetav pindala:', value="", flex=100)

    """Kolmas etapp on renoveerimislahenduse konfigureerimine."""
    et_konf = Step('Konfigureeri', views=['run_grasshopper', 'get_plotly_view', 'visualize_data'],
                   previous_label='Tagasi', next_label='Edasi')
    et_konf.sec_intro = Section('Sissejuhatus')
    et_konf.sec_intro.intro = Text('## Konfigureerimine \n'
                                   'Nüüd saad sa renoveerimislahenduste vahel valida ja erinevaid '
                                   'konfiguratsioone läbi mängida! \n\n'
                                   'Paremal pool ülemises ribas saad näha erinevaid '
                                   'arvutustulemusi, mis Sinu valitud konfiguratsiooni kohta käivad.\n\n'
                                   'Allpool on alajaotised erinevate renoveerimislahenduste valikutega.')
    et_konf.sec_intro.ehr = OutputField('EHR kood:', value=Lookup('et_intr.ehr'), flex=50)
    et_konf.sec_intro.typokood = OutputField('Hoone tüüp:', value=inferenceEngine.app_get_typo_kood, flex=50)

    et_konf.sec_pt = Section('Piirdetarindid')
    et_konf.sec_pt.selgitus1 = Text("## Piirdetarindid \n"
                                    "Kõige rohkem mõjutavad hoone toimivust selle piirdetarindid. "
                                    "Need elemendid määravad hoone kuju ja välimuse "
                                    "ning muuseas ka hoone soojapidavuse, õhupidavuse ja helipidavuse. "
                                    "Hoone piiretarindid on eriti olulised just energiatõhususe seisukohast.")
    et_konf.sec_pt.vs = OptionField('Vali uus välissein:', options=vslist, default=vslist[0], flex=100)
    et_konf.sec_pt.vs_kirj = OutputField('Lühikirjeldus', value=inferenceEngine.get_vs_kirjeldus, flex=100)
    #et_konf.sec_pt.vs_kirj2 = Text(value=Lookup('et_konf.sec_pt.vs_kirj'))
    et_konf.sec_pt.kl = OptionField('Vali uus katus:', options=kllist,
                                    default=kllist[0], flex=100)  # TODO Kaldkatuse kontroll/valik!
    et_konf.sec_pt.so = OptionField('Vali uus soklisein:', options=slist, default=slist[0], flex=100)

    et_konf.sec_pt.selgitus2 = Text("## Õhupidavus \n"
                                    "Vanemad hooned pole kuigi õhupidavad. Kõik õhk, mis hoonest välja läheb, "
                                    "viib endaga kaasa ka väärtusliku soojuse, mis planeeti kütab. "
                                    "Hoone õhupidavamaks muutmine parandab oluliselt ka selle energiatõhusust, "
                                    "mis väljendub madalamates küttekuludes.")
    et_konf.sec_pt.ohuleke = OptionField('Vali õhupidavus:', options=ohulekelist, default=ohulekelist[0],
                                         flex=100)
    # et_konf.sec_pt.ohuleke_vaartus = OutputField('Õhulekkearv (m³/(h·m²))', value=inferenceEngine.get_ohuleke_vaartus)

    et_konf.sec_pt.selgitus3 = Text("## Aknad ja uksed")
    et_konf.sec_pt.aken = OutputField('Vali akende tüüp:', value="Muutmata", flex=100)

    et_konf.sec_ts = Section('Tehnosüsteemid')
    et_konf.sec_ts.selgitus4 = Text("## Küttesüsteem")
    et_konf.sec_ts.kyte = OutputField('Vali küttesüsteemi tüüp:', value=ksyslist[0], flex=100)
    et_konf.sec_ts.kyte2 = OptionField('Vali soojusjaotuse tüüp:', options=kjaotuslist, default=kjaotuslist[0], flex=100)

    et_konf.sec_ts.selgitus5 = Text("## Ventilatsioon \n"
                                    "Kas ventilatsioonisüsteem on tsentraalne/trepikojapõhine/korteripõhine, "
                                    "sissepuhe ja/või väljatõmme")
    et_konf.sec_ts.vent = OptionField('Vali ventilatsiooni tüüp:', options=ventlist, default=ventlist[0], flex=100)

    et_konf.sec_ts.selgitus6 = Text("## Tugev- ja nõrkvool \n"
                                    "Pistikute hulk, kilpide asukohad, vask/valgus, kvaliteedi tase, ATS, fonolukk jms")
    et_konf.sec_ts.elekter = OutputField('Nõrkvoolupaigaldised:', value="-", flex=100)

    et_konf.sec_ts.selgitus7 = Text("## Jahutussüsteem")
    et_konf.sec_ts.jahutus = OutputField("Jahutussüsteem:", value="puudub")

    et_konf.sec_paike = Section('Taastuvenergia')
    et_konf.sec_paike.selgitus = Text("Lisa ehitisele päiksepaneelid või kollektorid")
    et_konf.sec_paike.voim = NumberField('Vali paneelide efektiivne tootmisvõimsus (kW):', variant='slider',
                                       min=0, max=50, flex=100)
    et_konf.sec_paike.markus = TextAreaField('Lisamärkused', flex=100)

    et_konf.sec_muu = Section('Muu')
    et_konf.sec_muu.selgitus4 = Text("## Rõdud ja lodžad")
    et_konf.sec_muu.markusrodud = TextAreaField('Lisamärkused', flex=100)

    et_konf.sec_muu.selgitus5 = Text("## Hoonevälised tööd")
    et_konf.sec_muu.markushooneval = TextAreaField('Lisamärkused', flex=100)

    """Viimane etapp on konfiguratsioonist lähteülesande dokumendi vormistamine."""
    et_tul = Step('Jaga', views=['get_pdf_view'], previous_label='Tagasi', next_label='...')


class Controller(ViktorController):
    """Kontrolleris luuakse väljundakende sisu."""

    label = 'My Entity Type'
    parametrization = Parametrization

    @MapView('Kaart', duration_guess=1)
    def get_map_view(self, params, **kwargs):
        # Make sure we have the latest data with the correct EHR code
        building_df = inferenceEngine.infer(params)[0]

        # Get the building location and address
        viitepunkt_lest = building_df['väärtus']['viitepunktXY']
        viitepunkt_lonlat = inferenceEngine.convert_coordinates(viitepunkt_lest[1], viitepunkt_lest[0], False)
        aadress = building_df['väärtus']['E3']

        # Create a point on the map
        markers = [
            MapPoint(viitepunkt_lonlat['x'], viitepunkt_lonlat['y'], description=aadress),
        ]

        # Visualize map
        features = markers
        return MapResult(features)

    @GeometryView('Digikaksik', duration_guess=10, update_label='Genereeri digikaksik', default_shadow=True)
    def run_grasshopper(self, params, **kwargs):
        # Create a JSON file from the input parameters
        input_json = (json.dumps(params.et_intr) + json.dumps(params.et_konf)).replace("}{", ", ")

        # Generate the input files
        files = [('input.json', BytesIO(bytes(input_json, 'utf8')))]

        # Run the Grasshopper analysis and obtain the output files
        generic_analysis = GenericAnalysis(files=files, executable_key="run_grasshopper",
                                           output_filenames=["geometry.3dm"])
        generic_analysis.execute(timeout=60)
        threedm_file = generic_analysis.get_output_file("geometry.3dm", as_file=True)

        return GeometryResult(geometry=threedm_file, geometry_type="3dm")

    @PlotlyView("Energiatõhusus", duration_guess=1)
    def get_plotly_view(self, params, **kwargs):
        # Make sure we have the latest data with the correct EHR code
        building_dfs = inferenceEngine.infer(params)
        building_df_synd = building_dfs[0]
        building_df_tana = building_dfs[1]
        building_df_konf = building_dfs[2]

        en_margis = building_df_synd['väärtus']['energiamargis']
        # Check if en_margis is None and assign default values if so
        if en_margis['tyyp'] is None:
            en_margis = {'tyyp': 'Puudub', 'arv': 0}

        '''
        # Assuming 'building_df' is defined and contains 'väärtus' column with needed components
        ruumide_kyte = building_df['väärtus']['ruumide_kyte']
        tarbevee_soojendamine = building_df['väärtus']['tarbevee_soojendamine']
        valgustid_seadmed_abielekter = building_df['väärtus']['valgustid_seadmed_abielekter']

        # Create a Figure
        fig = go.Figure()

        # Add the first three bars directly
        fig.add_trace(go.Bar(
            x=['TODO! Arvutuslik ETA esialgne, \n(RESTO + tüpoloogia andmed)',
               'Energiamärgis ' + en_margis['tyyp'],
               'TODO! Arvutuslik ETA täna, \n(RESTO + tänase olukorra konfiguratsiooni andmed)'],
            y=[10,  # Placeholder value
               en_margis['arv'],
               10],  # Placeholder value
            marker_color=['blue', 'red', 'blue']
        ))

        # Add the components of the fourth bar as separate traces for a stacked appearance
        fig.add_trace(go.Bar(
            x=['Arvutuslik ETA pärast renoveerimist'],
            y=[ruumide_kyte],
            name='Ruumide küte',
            marker_color='lightblue'
        ))

        fig.add_trace(go.Bar(
            x=['Arvutuslik ETA pärast renoveerimist'],
            y=[tarbevee_soojendamine],
            name='Tarbevee soojendamine',
            marker_color='lightgreen'
        ))

        fig.add_trace(go.Bar(
            x=['Arvutuslik ETA pärast renoveerimist'],
            y=[valgustid_seadmed_abielekter],
            name='Valgustid, seadmed, abielekter',
            marker_color='orange'
        ))

        # Adjust the layout to stack the bars representing components of the fourth value
        fig.update_layout(
            barmode='stack',
            title=go.layout.Title(text="Energiatõhusus")
        )

        '''
        fig = go.Figure(
            data=[go.Bar(x=['Arvutuslik ETA hoone ehitamisel',
                            'Arvutuslik ETA täna',
                            'Energiamärgis ' + en_margis['tyyp'],
                            'Arvutuslik ETA pärast renoveerimist'],
                         y=[building_df_synd['väärtus']['ETA'],
                            building_df_tana['väärtus']['ETA'],
                            en_margis['arv'],
                            building_df_konf['väärtus']['ETA']],
                         marker_color=['blue', 'blue', 'red', 'blue'])],
            layout=go.Layout(title=go.layout.Title(text="Energiatõhusus"))
        )
        return PlotlyResult(fig.to_json())

    @DataView("Hoone andmed", duration_guess=1)
    def visualize_data(self, params, **kwargs):
        # Make sure we have the latest data with the correct EHR code
        building_df = inferenceEngine.infer(params)[2]
        important_data = inferenceEngine.get_important_params(building_df)
        data = DataGroup(
            *[DataItem(str(row['Nimetus']), str(row['väärtus'])) for index, row in important_data.iterrows()][:100])

        return DataResult(data)

    @PDFView("Lähteülesande PDF", duration_guess=1)
    def get_pdf_view(self, params, **kwargs):
        file = File.from_url(url="https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf")
        return PDFResult(file=file)


# viktor-cli publish --registered-name reno-konfiguraator --tag v0.0.0
