import urllib
from io import BytesIO
import json
from pathlib import Path

import plotly.graph_objects as go
import pandas as pd
import requests

from viktor import ViktorController
from viktor.parametrization import ViktorParametrization, OutputField, NumberField, OptionField, LineBreak, \
    Text, Step, Lookup, Section, OptionField, BooleanField, TextField, TextAreaField
from viktor.external.generic import GenericAnalysis
from viktor.views import GeometryView, PDFView
from viktor.views import GeometryResult
from viktor.views import MapPolygon, MapPoint, MapResult, MapView
from viktor.views import PlotlyView, PlotlyResult
from viktor.views import DataGroup, DataItem, DataResult, DataView
from viktor import File
from viktor.views import PDFView, PDFResult

from viktor import ViktorController
from viktor.views import WebResult
from viktor.views import WebView

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
    et_intr = Step('Sissejuhatus', views=['get_kaart_view'], previous_label='...', next_label='Edasi')
    et_intr.intro = Text(
        '# Renokratt \n '
        'Renokratt on tark abiline korterelamute renoveerimise võimaluste läbimängimiseks. \n\n'
        'Renokrati eesmärk on vähendada renoveerimisprotsessi tegelikku '
        'ja tunnetatud keerukust ning leevendada renoveerimisega seotud väärarusaami. '
        'Renokratt võimaldab leida Sinu kodule kõige sobivama, kvaliteetsema ja odavama renoveerimislahenduse, '
        'mille põhjal luua konkreetne ja kvaliteetne lähteülesanne projekteerijale ja ehitajale. \n\n'
        'Alustamiseks sisesta vaid oma hoone aadress '
        'ja seejärel vajuta alumises paremas nurgas "Edasi" nupule.')
    et_intr.aad = TextField('Aadress', default='Akadeemia tee 4, Tallinn, Harju maakond', flex=100)
    # et_intr.ehr = NumberField('EHR kood', default=DEFAULT_EHR, flex=100)
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
    """et_intr.laiskadele = Text("1-464 paneelmaja: 101020350 \n\n"
                              "Tartu paneelmaja: 104018667 \n\n "
                              "Tallinna paneelmaja: 101010705 \n\n "
                              "Põlva kivimaja: 110009871 \n\n"
                              "Teadmata tüübiga hoone: 101027657")"""

    """Teine etapp on tänase olukorra täpsustamine ja EhR andmete parandamine."""
    et_par = Step('Kontroll', views=['get_aerofotod_view', 'run_grasshopper', 'visualize_data'],
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
    et_konf = Step('Konfigureerimine', views=['run_grasshopper', 'get_plotly_view', 'visualize_data'],
                   previous_label='Tagasi', next_label='Edasi')
    et_konf.sec_intro = Section('Sissejuhatus')
    et_konf.sec_intro.intro = Text('## Konfigureerimine \n'
                                   'Nüüd saad sa renoveerimislahenduste vahel valida ja erinevaid '
                                   'konfiguratsioone läbi mängida! \n\n'
                                   'Paremal pool ülemises ribas saad näha erinevaid '
                                   'arvutustulemusi, mis Sinu valitud konfiguratsiooni kohta käivad.\n\n'
                                   'Allpool on alajaotised erinevate renoveerimislahenduste valikutega.')
    # et_konf.sec_intro.ehr = OutputField('EHR kood:', value=Lookup('et_intr.ehr'), flex=50)
    et_konf.sec_intro.typokood = OutputField('Hoone tüüp:', value=inferenceEngine.app_get_typo_kood, flex=50)

    et_konf.sec_pt = Section('Piirdetarindid')
    et_konf.sec_pt.selgitus1 = Text("## Piirdetarindid \n"
                                    "Kõige rohkem mõjutavad hoone toimivust selle piirdetarindid. "
                                    "Need elemendid määravad hoone kuju ja välimuse "
                                    "ning muuseas ka hoone soojapidavuse, õhupidavuse ja helipidavuse. "
                                    "Hoone piiretarindid on eriti olulised just energiatõhususe seisukohast.")
    et_konf.sec_pt.vs = OptionField('Vali uus välissein:', options=vslist, default=vslist[0], flex=100)
    et_konf.sec_pt.vs_kirj = OutputField('Lühikirjeldus', value=inferenceEngine.get_vs_kirjeldus, flex=100)
    # et_konf.sec_pt.vs_kirj2 = Text(value=Lookup('et_konf.sec_pt.vs_kirj'))
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
    et_konf.sec_ts.kyte2 = OptionField('Vali soojusjaotuse tüüp:', options=kjaotuslist, default=kjaotuslist[0],
                                       flex=100)

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
    et_tul = Step('Jagamine', views=['get_pdf_view'], previous_label='Tagasi', next_label='...')


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

    @WebView('Maa-ameti kaart', duration_guess=1)
    def get_kaart_view(self, params, **kwargs):
        address = params.et_intr.aad
        address_info = inferenceEngine.get_address_info(address)
        viitepunkt_x = float(address_info.get("viitepunkt_x"))
        viitepunkt_y = float(address_info.get("viitepunkt_y"))

        html_content = f"""
        <!DOCTYPE HTML>
        <html>
        <head>
            <title>In-ADS komponent</title>
            <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
            <script type="text/javascript" src="https://inaadress.maaamet.ee/inaadress/js/inaadress.min.js?d=20220510"></script>
        </head>
        <body>
            <div id="InAadressDiv" style="width: 100%; height: 100vh"></div>
            <script>
                var inAadress = new InAadress({{
                    "container": "InAadressDiv",
                    "mode": 4,
                    "ihist": "1993",
                    "defaultBaseLayer": "ALUSKAART",
                    "baseLayers": ["ALUSKAART"],
                    "WMS": [],
                    "markers": {{
                        "bbox": [{viitepunkt_x - 200}, {viitepunkt_y - 200}, {viitepunkt_x + 200}, {viitepunkt_y + 200}],
                        "addresses": [{{
                            "ident": 0,
                            "x": "{viitepunkt_y}",
                            "y": "{viitepunkt_x}",
                            "title": "{address}"
                        }}]
                    }},
                    "labelMode": "label",
                    "appartment": 0,
                    "lang": "et"
                }});
            </script>
        </body>
        </html>
        """
        return WebResult(html=html_content)

    @WebView('Kitsendused', duration_guess=1)
    def get_kitsendused_view(self, params, **kwargs):
        url = f"https://kitsendused.maaamet.ee/#/avalik;ky=78405:501:2700"
        return WebResult(url=url)

    @WebView('Aerofotod', duration_guess=1)
    def get_aerofotod_view(self, params, **kwargs):
        address = params.et_intr.aad
        address_info = inferenceEngine.get_address_info(address)
        viitepunkt_x = float(address_info.get("viitepunkt_x"))
        viitepunkt_y = float(address_info.get("viitepunkt_y"))
        url = f"https://fotoladu.maaamet.ee/etak.php?x={viitepunkt_y}&y={viitepunkt_x}&view4"
        #print(url)
        return WebResult(url=url)

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

        eta_margis = en_margis['arv']
        eta_tana = building_df_tana['väärtus']['ETA']
        eta_konf = building_df_konf['väärtus']['ETA']

        en_margis_klass = en_margis['klass']
        eta_tana_klass = building_df_tana['väärtus']['R147']
        eta_konf_klass = building_df_konf['väärtus']['R147']

        colors = [inferenceEngine.get_eta_varv(eta_margis),
                  inferenceEngine.get_eta_varv(eta_tana),
                  inferenceEngine.get_eta_varv(eta_konf)]

        hover_texts = [
            f"Energiamärgis: {en_margis['tyyp']}<br>Väärtus: {eta_margis} kWh/m2/a<br>Klass: {en_margis_klass}"
            f"<br><br>KEK ehk kaalutud energiakasutus on ametlik <br>ja tegeliku energiatarbimise pealt arvutatud "
            f"<br>energiatõhususe näitaja. <br>See väärtus on võetud EhR-st.",
            f"Arvutuslik ETA täna<br>Väärtus: {eta_tana} kWh/m2/a<br>Klass: {eta_tana_klass}"
            f"<br><br>ETA väärtus on teoreetiline ehitusfüüsikalistele <br>printsiipidele toetuv energiatõhususe "
            f"näitaja. <br>See väärtus on arvutatud tüpoloogiliste <br>teadmiste ja sinu kontrollitud hoone "
            f"<br>andmete põhjal kasutades RESTO tööriista.",
            f"Arvutuslik ETA pärast renoveerimist<br>Väärtus: {eta_konf} kWh/m2/a<br>Klass: {eta_konf_klass}"
            f"<br><br>ETA väärtus on teoreetiline ehitusfüüsikalistele <br>printsiipidele toetuv energiatõhususe "
            f"näitaja. <br>See väärtus on arvutatud sinu valitud <br>renoveerimislahenduste põhjal kasutades "
            f"<br>RESTO tööriista.",
        ]

        fig = go.Figure(
            data=[go.Bar(
                x=['Energiamärgis ' + en_margis['tyyp'],
                   'Arvutuslik ETA täna',
                   'Arvutuslik ETA pärast renoveerimist'],
                y=[eta_margis, eta_tana, eta_konf],
                marker=dict(color=colors),
                text=[f"{eta_margis} ({en_margis_klass})",
                      f"{eta_tana} ({eta_tana_klass})",
                      f"{eta_konf} ({eta_konf_klass})"],
                hovertext=hover_texts,
                hoverinfo="text",
                textposition='auto',
                showlegend=False
            )],
            layout=go.Layout(
                title=go.layout.Title(text="Korterelamute energiatõhusus enne ja pärast renoveerimist"),
                xaxis=dict(title="Etapp"),
                yaxis=dict(title="Energiatõhususarv (kWh/m2/a)"),
                template='plotly_white',
                showlegend=True
            )
        )

        # Add horizontal lines for the threshold values
        threshold_values = [105, 125, 150]
        klassid = ["A", "B", "C"]
        annotations = ["A", "B", "C"]

        for i, value in enumerate(threshold_values):
            line_width = 4 if value == 150 else 2
            line_dash = "solid"  # Make all lines solid

            fig.add_shape(
                type="line",
                x0=-0.5,
                y0=value,
                x1=2.5,
                y1=value,
                line=dict(
                    color="LightSeaGreen",
                    width=line_width,
                    dash=line_dash,
                ),
            )
            fig.add_annotation(
                x=2.5,
                y=value,
                xref="x",
                yref="y",
                text=annotations[i],
                showarrow=False,
                font=dict(size=12, color="black"),
                align="left",
                xanchor="left",
                yanchor="top",
            )

        # Add legend manually for the colors
        fig.update_layout(
            legend=dict(
                title="Energiatõhususe klassid",
                itemsizing="constant"
            )
        )

        # Adding custom legend items
        color_scale = inferenceEngine.get_color_scale()
        for klass, color in color_scale.items():
            fig.add_trace(go.Scatter(
                x=[None], y=[None],
                mode='markers',
                marker=dict(size=10, color=color),
                legendgroup=klass,
                showlegend=True,
                name=klass
            ))

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
        file_path = Path(__file__).parent / 'teadmusbaas' / 'MKM_m3_lisa2.pdf'
        return PDFResult.from_path(file_path)

# viktor-cli publish --registered-name reno-konfiguraator --tag v0.0.0
