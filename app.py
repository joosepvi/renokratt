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

vslist = inferenceEngine.get_kb_excel_sheet('vs')['nimetus'].tolist()
ohulekelist = inferenceEngine.get_kb_excel_sheet('õhuleke')['nimetus'].tolist()

building_df = inferenceEngine.infer(DEFAULT_EHR)


class Parametrization(ViktorParametrization):
    """Kõik sisendväärtused, etapilisus ja väljundaknad tulevad selle klassi parameetritest."""

    """Esimene etapp on konkreetse renoveeritava hoone määramine."""
    etapp_1 = Step('Hoone valik', views=['get_map_view'], previous_label='...', next_label='Edasi')
    etapp_1.intro = Text(
        '# Renokratt \n '
        'Renokratt on tark abiline korterelamute renoveerimise lähteülesande loomiseks. \n\n'
        'Renokrati eesmärk on muuta renoveerimise ettevõtmine lihtsamaks, vähendada renoveerimisprotsessi tegelikku '
        'ja tunnetatud keerukust ning leevendada renoveerimisega seotud väärarusaami. '
        'Renokratt aitab Sul leida just Sinu hoonele kõige sobivama renoveerimislahenduse '
        'ning võimaldab Sul luua võimalikult konkreetse ja kvaliteetse lähteülesande projekteerijale ja ehitajale. \n\n'
        'Alustamiseks sisesta vaid oma hoone Ehitusregistri kood (selle leiad aadressilt ehr.ee) '
        'ja seejärel vajuta alumises paremas nurgas "Edasi" nupule.')
    etapp_1.ehr = NumberField('EHR kood', default=DEFAULT_EHR, flex=100)
    etapp_1.lb1 = LineBreak()
    etapp_1.tyyp = OutputField('Hoone tüüp:', value=inferenceEngine.app_get_typo_kood, flex=100)
    etapp_1.selgitus = Text("Käesolev tööriist on välja töötatud enne 1990ndat aastat ehitatud telliskivist, "
                            "plokkidest ja raudbetoonpaneelidest korterelamutele. \n"
                            "Juhul kui valitud hoone tüüp ei ole teada, siis võib programmis esineda vigu.")
    etapp_1.lb2 = LineBreak()
    etapp_1.laiskadele = Text("1-464 paneelmaja: 101020350 \n\n"
                              "Tartu paneelmaja: 104018667 \n\n "
                              "Tallinna paneelmaja: 101010705 \n\n "
                              "Põlva kivimaja: 110009871 \n\n"
                              "Teadmata tüübiga hoone: 101027657")

    """Teine etapp on renoveerimislahenduse konfigureerimine."""
    etapp_2 = Step('Konfigureerimine', views=['run_grasshopper', 'get_plotly_view', 'visualize_data'],
                   previous_label='Tagasi', next_label='Edasi')
    etapp_2.sec_intro = Section('Sissejuhatus')
    etapp_2.sec_intro.intro = Text('## Konfigureerimine \n'
                                   'Nüüd saad sa renoveerimislahenduste vahel valida ja erinevaid '
                                   'konfiguratsioone läbi mängida! \n\n'
                                   'Paremal pool ülemises ribas saad näha erinevaid '
                                   'arvutustulemusi, mis Sinu valitud konfiguratsiooni kohta käivad.\n\n'
                                   'Allpool on kategoriseeritud erinevad alajaotised '
                                   'erinevate renoveerimislahenduste valikutega.')
    etapp_2.sec_intro.ehr = OutputField('EHR kood:', value=Lookup('etapp_1.ehr'))

    etapp_2.sec_olol = Section('Eelnevalt teostatud tööd')
    etapp_2.sec_olol.katkate = BooleanField('Kas katusekate on vahetatud?', flex=100)
    etapp_2.sec_olol.katsooj = BooleanField('Kas katuslage või pööningut on täiendavalt soojustatud?', flex=100)
    etapp_2.sec_olol.vssooj = OptionField('Kas välisseinasid on soojustatud?',
                                          options=['Ei', 'Otsaseinad', 'Terve hoone'], flex=100)
    etapp_2.sec_olol.soksooj = BooleanField('Kas soklit on soojustatud?', flex=100)
    etapp_2.sec_olol.silriba = BooleanField('Kas sillutisriba on uuendatud?', flex=100)
    etapp_2.sec_olol.sooj = NumberField('Kui suur osa akendest on vahetatud? (ligikaudne vahetuse %)', variant='slider',
                                        min=0, max=100, flex=100)
    etapp_2.sec_olol.kytsys = BooleanField('Kas küttesüsteem on rekonstrueeritud?', flex=100)
    etapp_2.sec_olol.veetor = BooleanField('Kas veetorustik on vahetatud?', flex=100)
    etapp_2.sec_olol.kantor = BooleanField('Kas kanalisatsioonitorustik on vahetatud?', flex=100)
    etapp_2.sec_olol.elsys = BooleanField('Kas elektrisüsteem on uuendatud?', flex=100)
    etapp_2.sec_olol.toltokestus = BooleanField('Kas on teostatud tuletõkesutstöid?', flex=100)
    etapp_2.sec_olol.markused = TextAreaField('Lisamärkused', flex=100)

    etapp_2.sec_pt = Section('Piirdetarindid')
    etapp_2.sec_pt.selgitus1 = Text("## Piirdetarindid \n"
                                    "Kõige rohkem mõjutavad hoone toimivust selle piirdetarindid. "
                                    "Need elemendid määravad hoone kuju ja välimuse "
                                    "ning muuseas ka hoone soojapidavuse, õhupidavuse ja helipidavuse. "
                                    "Hoone piiretarindid on eriti olulised just energiatõhususe seisukohast.")
    etapp_2.sec_pt.vs = OptionField('Vali uus välissein:', options=vslist, default=vslist[0], flex=100)
    # etapp_2.sec_pt.vs_u = OutputField('Valitud seina soojusläbivus (W/(m²K))', value=inferenceEngine.get_vs_u)
    # etapp_2.sec_pt.vs_paksus = OutputField('Valitud seina paksus (mm)', value=inferenceEngine.get_vs_paksus)
    etapp_2.sec_pt.kl = OptionField('Vali uus katus:', options=vslist,
                                    default=vslist[0], flex=100)  # TODO Kaldkatuse kontroll/valik!
    etapp_2.sec_pt.so = OptionField('Vali uus soklisein:', options=vslist, default=vslist[0], flex=100)

    etapp_2.sec_pt.selgitus2 = Text("## Õhupidavus \n"
                                    "Vanemad hooned pole kuigi õhupidavad. Kõik õhk, mis hoonest välja läheb, "
                                    "viib endaga kaasa ka väärtusliku soojuse, mis planeeti kütab. "
                                    "Hoone õhupidavamaks muutmine parandab oluliselt ka selle energiatõhusust, "
                                    "mis väljendub madalamates küttekuludes.")
    etapp_2.sec_pt.ohuleke = OptionField('Vali õhupidavus:', options=ohulekelist, default=ohulekelist[0],
                                         flex=100)
    # etapp_2.sec_pt.ohuleke_vaartus = OutputField('Õhulekkearv (m³/(h·m²))', value=inferenceEngine.get_ohuleke_vaartus)

    etapp_2.sec_pt.selgitus3 = Text("## Aknad ja uksed")
    etapp_2.sec_pt.aken = OptionField('Vali akende tüüp:', options=vslist, default=vslist[0], flex=100)

    etapp_2.sec_ts = Section('Tehnosüsteemid')
    etapp_2.sec_ts.selgitus4 = Text("## Küttesüsteem")
    etapp_2.sec_ts.kyte = OptionField('Vali küttesüsteemi tüüp:', options=vslist, default=vslist[0], flex=100)

    etapp_2.sec_ts.selgitus5 = Text("## Ventilatsioon \n"
                                    "Kas ventilatsioonisüsteem on tsentraalne/trepikojapõhine/korteripõhine, "
                                    "sissepuhe ja/või väljatõmme")
    etapp_2.sec_ts.vent = OptionField('Vali ventilatsiooni tüüp:', options=vslist, default=vslist[0], flex=100)

    etapp_2.sec_ts.selgitus6 = Text("## Tugev- ja nõrkvool \n"
                                    "Pistikute hulk, kilpide asukohad, vask/valgus, kvaliteedi tase, ATS, fonolukk jms")
    etapp_2.sec_ts.elekter = OptionField('Vali midagi:', options=vslist, default=vslist[0], flex=100)

    etapp_2.sec_muu = Section('Muu')
    etapp_2.sec_muu.selgitus4 = Text("## Rõdud ja lodžad")

    etapp_2.sec_muu.selgitus5 = Text("## Hoonevälised tööd")

    """Kolmas etapp on konfiguratsioonist lähteülesande dokumendi vormistamine."""
    etapp_3 = Step('Lähteülesanne', views=['get_pdf_view'], previous_label='Tagasi', next_label='...')


class Controller(ViktorController):
    """Kontrolleris luuakse väljundakende sisu."""

    label = 'My Entity Type'
    parametrization = Parametrization

    @MapView('Kaart', duration_guess=1)
    def get_map_view(self, params, **kwargs):
        # Make sure we have the latest data with the correct EHR code
        building_df = inferenceEngine.infer(params.etapp_1.ehr)

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
        input_json = (json.dumps(params.etapp_1) + json.dumps(params.etapp_2)).replace("}{", ", ")

        # Generate the input files
        files = [('input.json', BytesIO(bytes(input_json, 'utf8')))]

        # Run the Grasshopper analysis and obtain the output files
        generic_analysis = GenericAnalysis(files=files, executable_key="run_grasshopper",
                                           output_filenames=["geometry.3dm"])
        generic_analysis.execute(timeout=60)
        threedm_file = generic_analysis.get_output_file("geometry.3dm", as_file=True)

        return GeometryResult(geometry=threedm_file, geometry_type="3dm")

    @DataView("Hoone andmed", duration_guess=1)
    def visualize_data(self, params, **kwargs):
        # Make sure we have the latest data with the correct EHR code
        building_df = inferenceEngine.infer(params.etapp_1.ehr)

        data = DataGroup(*[DataItem(str(row['Nimetus']), str(row['väärtus'])) for index, row in building_df.iterrows()][:100])

        return DataResult(data)

    @PlotlyView("Energiatõhusus", duration_guess=1)
    def get_plotly_view(self, params, **kwargs):
        # Make sure we have the latest data with the correct EHR code
        building_df = inferenceEngine.infer(params.etapp_1.ehr)
        en_margis = building_df['väärtus']['energiamargis']
        # Check if en_margis is None and assign default values if so
        if en_margis['tyyp'] is None:
            en_margis = {'tyyp': 'Puudub', 'arv': 0}

        fig = go.Figure(
            data=[go.Bar(x=['TODO! Arvutuslik ETA esialgne, \n(RESTO + tüpoloogia andmed)',
                            'Energiamärgis ' + en_margis['tyyp'],
                            'TODO! Arvutuslik ETA täna, \n(RESTO + tänase olukorra konfiguratsiooni andmed)',
                            'TODO! Arvutuslik ETA pärast renoveerimist, \n(RESTO + perspektiivse konfiguratsiooni andmed)'],
                         y=[400,  # TODO Arvutada RESTOga kasutades tüpoloogia andmeid
                            en_margis['arv'],
                            400,  # TODO Arvutada RESTOga kasutades konfiguratsiooni andmeid
                            400])],  # TODO Arvutada RESTOga kasutates konfiguratsiooni andmeid
            layout=go.Layout(title=go.layout.Title(text="Energiatõhusus"))
        )
        return PlotlyResult(fig.to_json())

    @PDFView("Lähteülesande PDF", duration_guess=1)
    def get_pdf_view(self, params, **kwargs):
        file = File.from_url(url="https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf")
        return PDFResult(file=file)

# viktor-cli publish --registered-name reno-konfiguraator --tag v0.0.0
