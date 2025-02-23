import urllib
from tokenize import String

import pandas as pd
import numpy as np
import resto as resto
import requests
import json
import math
from datetime import datetime
from pathlib import Path
from functools import lru_cache

# Current file's directory (app.py's location)
app_dir = Path(__file__).parent

muutujad_path = app_dir / "teadmusbaas" / "muutujad.xlsx"
kb_path = app_dir / "teadmusbaas" / "teadmusbaas.xlsx"
korterelamud_path = app_dir / "teadmusbaas" / "eesti-korterelamud.xlsx"
typo_path = app_dir / "teadmusbaas" / "tüpoloogia.xlsx"

df_vs = pd.read_excel(kb_path, sheet_name='vs')
df_ohuleke = pd.read_excel(kb_path, sheet_name='õhuleke')
df_korterelamud = pd.read_excel(korterelamud_path, sheet_name='Ilma>1995')
df_typoloogia = pd.read_excel(typo_path, sheet_name="Tüpoloogia tabel")

ehr_url = "https://livekluster.ehr.ee/api/building/v2/buildingData"
digikaksik_url = "https://livekluster.ehr.ee/api/3dtwin/v1/rest-api/particles?bbox=542914.54,6589115.305,542915.54,6589116.305"
maaamet_url = "https://gpa.maaamet.ee/api/"  # Maa-ameti Geodeesia teenused
resto_url = "https://resto-tools-r-a7308bf2697d.herokuapp.com/"

YMBRUSE_R = 100


@lru_cache(maxsize=128)  # Adjust maxsize according to your needs
def get_address_info(address):
    encoded_address = urllib.parse.quote(address)  # URL-encode the address
    json_url = f"https://inaadress.maaamet.ee/inaadress/gazetteer?address={encoded_address}"
    #print(json_url)
    response = requests.get(json_url)
    first_address = response.json()["addresses"][0]
    return first_address


def get_ehr_kood(address):
    address_info = get_address_info(address)
    ehr_kood = int(address_info.get("tunnus"))
    return ehr_kood


@lru_cache(maxsize=128)  # Adjust maxsize according to your needs
def get_ehr_response(ehr_kood):
    start_time = datetime.now()  # Start timing for feedback
    response = requests.get(ehr_url + '?ehr_code=' + str(ehr_kood))
    #print("get_ehr runtime: ", datetime.now() - start_time)
    return json.loads(response.text)


@lru_cache(maxsize=128)
def get_resto_respone(json_data):
    start_time = datetime.now()  # Start timing for feedback

    resto_request_url = resto_url + 'getFullRestoResponseDF' + '?json_data=' + str(json_data)
    response = requests.get(resto_request_url)
    response_json = json.loads(response.text)

    #print(json_data)
    #print("get_resto runtime: ", datetime.now() - start_time)
    return response_json


# Function to cache and read an Excel file, returning a pandas DataFrame of the entire file
@lru_cache(maxsize=None)
def read_excel_file_cached(file_path):
    return pd.ExcelFile(file_path)


# Function to read a specific sheet from the cached Excel file
def read_excel_sheet(file_path, sheet_name):
    excel_file = read_excel_file_cached(file_path)
    return excel_file.parse(sheet_name)


def get_muutujad_excel_sheet(sheet_name):
    return read_excel_sheet(muutujad_path, sheet_name)


def get_kb_excel_sheet(sheet_name):
    return read_excel_sheet(kb_path, sheet_name)


def get_kb_kirjeldus(sheet_name, nimi):
    sh_content_df = get_kb_excel_sheet(sheet_name)
    #kirjeldus = str(sh_content_df.loc[nimi, 'Lühikirjeldus'])
    kirjeldus = str(sh_content_df[sh_content_df['Nimetus'] == nimi]['Lühikirjeldus'].values[0])
    return kirjeldus


def get_vs_kirjeldus(params, **kwargs):
    nimi = params.et_konf.sec_pt.vs
    kb_vs_kirjeldus = get_kb_kirjeldus("vs", nimi)
    return kb_vs_kirjeldus

@lru_cache(maxsize=None)
def get_typo_kood(ehr_kood):
    try:
        t = df_korterelamud.loc[df_korterelamud['EHR kood'] == ehr_kood, 'T_kood'].iloc[0]
    except:
        t = 'Pole teada'
    return t


def app_get_typo_kood(params, **kwargs):
    #return get_typo_kood(params.et_intr.ehr)
    return get_typo_kood(get_ehr_kood(params.et_intr.aad))


def get_typo_df(typo_kood):
    """Tüpooloogia Excelist kõikide tüpoloogiat iseloomustavate statistiliste parameetrite toomine."""
    if typo_kood == 'Pole teada' or typo_kood is None:
        return None
    df = (df_typoloogia.loc[:, ['Nimetus', 'Ühik', 'Tähis', typo_kood]]
          .ffill()
          .set_index('Tähis')
          .rename(columns={typo_kood: 'väärtus'})
          .drop(['T61', 'T62']))  # Ebaolulised
    return df


def get_building_ehr_info(ehr_kood):
    """Toome kõik EhR-i avaandmed ühte DataFrame'i"""
    start_time = datetime.now()  # Start timing for feedback

    ehr_json = get_ehr_response(ehr_kood)

    ruumikuju = ehr_json['ehitis']['ehitiseKujud']['ruumikuju'][0]
    geometry = ruumikuju['geometry']
    viitepunkt_x = float(ruumikuju['viitepunktX'])
    viitepunkt_y = float(ruumikuju['viitepunktY'])
    maakond = ruumikuju['ehitiseKujuAadressid']['aadress'][0]['tase1_nimetus']
    kov = ruumikuju['ehitiseKujuAadressid']['aadress'][0]['tase2_nimetus']
    taisaadress = ehr_json['ehitis']['ehitiseAndmed']['taisaadress']
    esmanekasutus = ehr_json['ehitis']['ehitiseAndmed']['esmaneKasutus']
    kasutusotstarve_kood = int(ehr_json['ehitis']['ehitiseKasutusotstarbed']['kasutusotstarve'][0]['kaosKood'])
    kasutusotstarve_tekst = ehr_json['ehitis']['ehitiseKasutusotstarbed']['kasutusotstarve'][0]['kaosIdTxt']

    # Ehitise tehniliste näitajate default väärtused
    valisseina_liik = "puudub"
    kandekonstr_mat = "puudub"
    valissein_viimistlus = "puudub"
    soojusvarustuse_liik = "puudub"
    soojusallika_liik = "puudub"
    energiaallika_liik = "puudub"
    ventilatsiooni_liik = "puudub"
    jahutuse_liik = "puudub"
    gaas = "puudub"

    for tehn_naitaja in ehr_json['ehitis']['ehitiseTehnilisedNaitajad']['tehnilineNaitaja']:
        if tehn_naitaja['klNimetus'] == 'Välisseina liik':
            valisseina_liik = tehn_naitaja['nimetus']
        elif tehn_naitaja['klNimetus'] == 'Kande- ja jäigastavate konstruktsioonide materjal':
            kandekonstr_mat = tehn_naitaja['nimetus']
        elif tehn_naitaja['klNimetus'] == 'Välisseina välisviimistluse materjal':
            valissein_viimistlus = tehn_naitaja['nimetus']
        elif tehn_naitaja['klNimetus'] == 'Soojusvarustuse liik':
            soojusvarustuse_liik = tehn_naitaja['nimetus']
        elif tehn_naitaja['klNimetus'] == 'Soojusallikas':
            soojusallika_liik = tehn_naitaja['nimetus']
        elif tehn_naitaja['klNimetus'] == 'Energiaallikas':
            energiaallika_liik = tehn_naitaja['nimetus']
        elif tehn_naitaja['klNimetus'] == 'Ventilatsiooni liik':
            ventilatsiooni_liik = tehn_naitaja['nimetus']
        elif tehn_naitaja['klNimetus'] == 'Jahutussüsteemi liik':
            jahutuse_liik = tehn_naitaja['nimetus']
        elif tehn_naitaja['klNimetus'] == 'Võrgu- või mahutigaasi olemasolu':
            gaas = tehn_naitaja['nimetus']

    all_coords = geometry['coordinates'][0]
    min_x = min(coord[0] for coord in all_coords) + 1
    max_x = max(coord[0] for coord in all_coords) - 1
    min_y = min(coord[1] for coord in all_coords) + 1
    max_y = max(coord[1] for coord in all_coords) - 1
    avg_x = (min_x + max_x) / 2
    avg_y = (min_y + max_y) / 2
    bbox = "{},{},{},{}".format(avg_x, avg_y, avg_x + 1, avg_y + 1)
    bbox_ymbrus = "{},{},{},{}".format(avg_x - YMBRUSE_R, avg_y - YMBRUSE_R, avg_x + YMBRUSE_R, avg_y + YMBRUSE_R)

    max_korruste_arv = int(ehr_json['ehitis']['ehitisePohiandmed']['maxKorrusteArv'])
    ehitisalune_pind = float(ehr_json['ehitis']['ehitisePohiandmed']['ehitisalunePind'])
    netopind = float(ehr_json['ehitis']['ehitisePohiandmed']['suletud_netopind'])
    maaaluste_korruste_arv = abs(int(ehr_json['ehitis']['ehitisePohiandmed'].get('maaalusteKorrusteArv', 0)))

    energiamargised = ehr_json['ehitis']['ehitiseEnergiamargised']['energiamargis']
    if energiamargised:
        energiamargis = ehr_json['ehitis']['ehitiseEnergiamargised']['energiamargis'][0]
        etakek_tyyp = energiamargis['etaKekType']
        try:
            etakek_value = float(energiamargis['etaKekVal'])
        except:
            etakek_value = None
        energaklass = energiamargis['energiaKlass']
        try:
            koetav_pind = float(energiamargised[0].get('koetavPind', netopind))
        except:
            koetav_pind = None
        if koetav_pind is None:
            koetav_pind = netopind
        elif koetav_pind == 0:
            koetav_pind = netopind
    else:
        etakek_tyyp = None
        etakek_value = None
        energaklass = None
        koetav_pind = netopind

    '''RESTO sisendid:
                ['E1', 'E3', 'E6', 'E7', 'E10', 'E11', 'E12', 'E19',
                'E21', 'E25', 'E26', 'E27', 'E28', 'E29', 'E30', 'E31', 'E32', 'E33',
                'L6', 'L9', 'L11', 'L12', 'L13', 'L14', 'L15', 'L16', 'L17', 'L18', <- pindalad leiame hiljem
                'L21', 'L22', 'L24', 'L26', 'L27', <- joonkülmasillad leiame hiljem
                'T8', 'T11', <- uste pindala ja kinnituste pikkus kokku
                'T12', 'T13', 'T15', 'T17', 'T18', 'T19', 'T20', 'T22', 'T24', 'T25', 'T26', 'T27', <- soojusläbivused
                'T41', 'R312', 'R313', 'R314', 'R315', 'R316', 'R317', 'R318', 'R319', <- akende ja fas pindalade suhe
                'C1', 'C2', 'C66', 'C67', 'C34', 'C35', 'C41', 'C42', 'R63'] <- resto.get_defaults()'''
    ehitise_andmed = pd.Series({'E1': ehr_kood,
                                'bbox': bbox,
                                'bbox_ymbrus': bbox_ymbrus,
                                'viitepunktXY': [viitepunkt_x, viitepunkt_y],
                                'energiamargis': {'tyyp': etakek_tyyp, 'arv': etakek_value, 'klass': energaklass},
                                'E3': taisaadress,
                                'E4': maakond,
                                'E5': kov,
                                'E6': kasutusotstarve_kood,
                                'E7': kasutusotstarve_tekst,
                                'E9': ehitisalune_pind,
                                'E10': max_korruste_arv,
                                'E11': maaaluste_korruste_arv,
                                'E12': esmanekasutus,
                                'E19': netopind,
                                'E21': koetav_pind,
                                'E25': valisseina_liik,
                                'E26': kandekonstr_mat,
                                'E27': valissein_viimistlus,
                                'E28': soojusvarustuse_liik,
                                'E29': soojusallika_liik,
                                'E30': energiaallika_liik,
                                'E31': ventilatsiooni_liik,
                                'E32': jahutuse_liik,
                                'E33': gaas,
                                }, name='väärtus')

    # print("get_building_ehr_info() runtime: ", datetime.now() - start_time)
    # return Pandas.Series type
    return ehitise_andmed


def get_building_geometry_values_test(bbox):
    """
    Funktsioon, mis arvutab hoone geomeetria väärtused, kasutades bounding box'i (bbox).
    Rhino geomeetriast sõltuvust pole - töötleme Maa-ameti API andmeid otseselt.
    """

    # --- Samm 1: Fetch geomeetria Maa-ameti API-st ---
    def fetch_building_geometry(bbox):
        """Fetches building geometry from the 3D Twin API."""
        url = f"https://livekluster.ehr.ee/api/3dtwin/v1/rest-api/particles?bbox={bbox}"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                response_data = response.read().decode('utf-8')
                json_data = json.loads(response_data)
            return json_data  # Tagastame JSON-andmed otse
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"HTTP Error: {e.code}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"URL Error: {e.reason}")
        except Exception as e:
            raise RuntimeError(str(e))

    # --- Samm 2: Sorteerime geomeetria osadeks ---
    def sort_geometry(buildings):
        """
        Sorteerib geomeetria osadeks (seinad, maapind, tasased katused, kaldkatused).
        Kasutatakse normaalvektoreid ja pindade kõrgusi (Z-koordinaate).
        """
        walls = []
        ground = []
        flat_roofs = []
        sloped_roofs = []
        sloped = False

        # Parameetrid
        vertical_tolerance = 0.1  # Seinad (peaaegu vertikaalne)
        ground_tolerance = 1.0    # Maapinna määramine (kõrgus erinevus)
        roof_angle_threshold = 15  # Katuse kaldkraadid

        # Aitab arvutada normaalvektori ja Z-telje vahelise nurga kraadides
        def angle_with_z_axis(nx, ny, nz):
            # Normaliseerime normaalvektori
            magnitude = math.sqrt(nx**2 + ny**2 + nz**2)
            nx, ny, nz = nx / magnitude, ny / magnitude, nz / magnitude
            # Leiame nurga kraadides Z-teljega
            dot_product = abs(nz)  # Z-komponent määrab kaldenurga
            angle_rad = math.acos(dot_product)
            return math.degrees(angle_rad)

        # Läbime kõik hooneosad ja klassifitseerime need
        for building in buildings:
            particles = building.get('particles', [])
            for particle in particles:
                # Võtame kolm punkti (x0, y0, z0), (x1, y1, z1), (x2, y2, z2)
                x0, y0, z0 = particle.get('x0'), particle.get('y0'), particle.get('z0')
                x1, y1, z1 = particle.get('x1'), particle.get('y1'), particle.get('z1')
                x2, y2, z2 = particle.get('x2'), particle.get('y2'), particle.get('z2')

                # Arvutame pindala normaali (ristvektor kahe külje vahel)
                ux, uy, uz = x1 - x0, y1 - y0, z1 - z0
                vx, vy, vz = x2 - x0, y2 - y0, z2 - z0
                nx, ny, nz = (uy * vz - uz * vy), (uz * vx - ux * vz), (ux * vy - uy * vx)

                # Nurk Z-teljega
                angle = angle_with_z_axis(nx, ny, nz)

                # Arvutame pinna keskmise Z-koordinaadi
                avg_z = (z0 + z1 + z2) / 3.0

                # Klassifitseerime pindala
                if angle < vertical_tolerance:  # Peaaegu vertikaalne (seinad)
                    walls.append((nx, ny, nz, avg_z))
                elif angle < roof_angle_threshold:  # Tasane katus
                    flat_roofs.append((nx, ny, nz, avg_z))
                else:  # Kaldu (maapind või kaldkatus)
                    if avg_z < ground_tolerance:  # Lähedal maapinnale
                        ground.append((nx, ny, nz, avg_z))
                    else:
                        sloped_roofs.append((nx, ny, nz, avg_z))

        if sloped_roofs:
            sloped = True  # Hoone sisaldab kaldkatuseid

        return walls, ground, flat_roofs, sloped_roofs, sloped

    # --- Samm 3: Arvutame pindalad ja suunad ---
    def calculate_parameters(walls, ground, flat_roofs, sloped_roofs, sloped):
        """
        Arvutab pindalade ja suundade põhjal vajalikud parameetrid.
        """
        def calculate_total_area(elements):
            """Summeerib pindalade kogupindala."""
            total_area = 0.0
            for element in elements:
                nx, ny, nz, avg_z = element  # Normaali vektor ja pindala kõrgus
                area = math.sqrt(nx**2 + ny**2 + nz**2)  # Pindala on normaali suurus
                total_area += area
            return total_area

        def classify_wall_directions(walls):
            """Klassifitseerib seinad vastavalt ilmakaartele."""
            directions = {f"L{i}": 0.0 for i in range(11, 19)}  # L11-L18
            for wall in walls:
                nx, ny, nz, avg_z = wall  # Normaali vektor ja pindala kõrgus
                angle = math.degrees(math.atan2(ny, nx))  # Suund ilmakaarte järgi
                if angle < 0:
                    angle += 360
                if 337.5 <= angle or angle < 22.5:
                    directions["L11"] += 1
                elif 22.5 <= angle < 67.5:
                    directions["L12"] += 1
                elif 67.5 <= angle < 112.5:
                    directions["L13"] += 1
                elif 112.5 <= angle < 157.5:
                    directions["L14"] += 1
                elif 157.5 <= angle < 202.5:
                    directions["L15"] += 1
                elif 202.5 <= angle < 247.5:
                    directions["L16"] += 1
                elif 247.5 <= angle < 292.5:
                    directions["L17"] += 1
                elif 292.5 <= angle < 337.5:
                    directions["L18"] += 1
            return directions

        # Arvutame pindalad
        total_wall_area = calculate_total_area(walls)
        total_roof_area = calculate_total_area(flat_roofs) + calculate_total_area(sloped_roofs)
        total_ground_area = calculate_total_area(ground)

        # Klassifitseerime seinad suundade järgi
        wall_directions = classify_wall_directions(walls)

        return {
            "L5": total_wall_area,  # Seinad
            "L6": total_roof_area,  # Katused
            "L9": total_ground_area,  # Maapind
            **wall_directions  # Seinte suunad
        }

    # --- Samm 4: Integreeri kõik ---
    buildings = fetch_building_geometry(bbox)
    walls, ground, flat_roofs, sloped_roofs, sloped = sort_geometry(buildings)
    calculated_parameters = calculate_parameters(walls, ground, flat_roofs, sloped_roofs, sloped)

    # --- Tagasta tulemused Pandas Series kujul ---
    ps = pd.Series(calculated_parameters, name='väärtus')
    print("SIIIIIN")
    print(ps)
    return ps




def get_building_geometry_values():
    # TODO: Arvuta erinevatesse ilmakaartesse vaatavad seinad.
    """''L6', 'L9', 'L11', 'L12', 'L13', 'L14', 'L15', 'L16', 'L17', 'L18', <- pindalad leiame hiljem
    L21', 'L22', 'L24', 'L26', 'L27', <- joonkülmasillad leiame hiljem
    'T8', 'T11', <- uste pindala ja kinnituste pikkus kokku
    'T12', 'T13', 'T15', 'T17', 'T18', 'T19', 'T20', 'T22', 'T24', 'T25', 'T26', 'T27', <- soojusläbivused
    'T41', 'R312', 'R313', 'R314', 'R315', 'R316', 'R317', 'R318', 'R319', <- akende ja fas pindalade suhe"""

    # Placeholder väärtused võetud Elisa Iliste tehnilise passi scriptist, hoone 101020350
    ps = pd.Series({
        "L5": 2641.387088,  # Fassaadi pindala
        "L6": 539.6,  # Katuslae pindala kokku, m2
        "L7": 0,  # Katuslae pindala
        "L8": 0.0,  # Pööningu vahelae pindala kokku, m2
        "L9": 539.64,  # Pinnasel põranda pindala kokku, m2
        "L10": 0.0,  # Kütmata keldri lae pindala kokku, m2
        "L11": 233.6,  # N fassaadi pindala kokku, m2
        "L12": 0.0,  # NE fassaadi pindala kokku, m2
        "L13": 1299.1,  # E fassaadi pindala kokku, m2
        "L14": 0.0,  # SE fassaadi pindala kokku, m2
        "L15": 233.6,  # S fassaadi pindala kokku, m2
        "L16": 0.0,  # SW fassaadi pindala kokku, m2
        "L17": 1269.1,  # W fassaadi pindala kokku, m2
        "L18": 0.0,  # NW fassaadi pindala kokku, m2
        "L19": 10,  # Ehitusaluse pinna välisnurkade arv
        "L20": 5,  # Ehitusaluse pinna sisenurkade arv
        "L21": 392.32,  # VS-VS liitekoha pikkus kokku, m
        "L22": 184.22,  # VS-KL liitekoha pikkus kokku, m
        "L23": 0.0,  # VS-PööninguVL liitekoha pikkus kokku, m
        "L24": 141.04,  # VS-PP liitekoha pikkus kokku, m
        "L25": 0.0,  # VS-KeldriVL liitekoha pikkus kokku, m
        "L26": 987.28,  # VS-VL liitekoha pikkus kokku, m
        "L27": 608.4,  # VS-SS liitekoha pikkus kokku, m
        "R1": 62.623933008,  # N akende arvutuspindala, m2
        "R2": 0.0,  # NE akende arvutuspindala, m2
        "R3": 348.2652027856,  # E akende arvutuspindala, m2
        "R4": 0.0,  # SE akende arvutuspindala, m2
        "R5": 62.623933008,  # S akende arvutuspindala, m2
        "R6": 0.0,  # SW akende arvutuspindala, m2
        "R7": 340.2227456356,  # W akende arvutuspindala, m2
        "R8": 0.0,  # NW akende arvutuspindala, m2
        "R9": 3011.64,  # Välisseina arvutuspindala ilma akende ja usteta, m2
        "T11": 1862.42  # Hoone akna- ja ukse seinakinnituse pikkus kokku, m
    }, name='väärtus')

    return ps


def get_building_df(ehr_kood):
    """Paneme kõikide erinevate allikate andmed ühte DataFrame-i"""
    start_time = datetime.now()  # Start timing for feedback

    ehr_andmed = get_building_ehr_info(ehr_kood)

    # Hoone tüpoloogia tunnuskood, alati str
    typo_kood = get_typo_kood(ehr_kood)

    # Tunnuskoodile vastavad statistilised andmed DataFrame-ina, võib olla None kui tüüp pole teada
    typo_df = get_typo_df(typo_kood)

    if typo_df is None:  # Tüpoloogia koodile vastavaid tüüpandmeid pole.
        typo_andmed = None
        andmed2 = pd.Series({
            'T1': typo_kood,
        }, name='väärtus')
    else:
        typo_andmed = typo_df.rename(columns={typo_kood: 'väärtus'})

        trepikodade_arv = resto.get_trepikodade_arv(ehr_andmed)
        andmed2 = pd.Series({
            'T1': typo_kood,
            'E8': int(trepikodade_arv),
            'T8': float(trepikodade_arv * typo_andmed['väärtus']['T54'] * typo_andmed['väärtus']['T55']),
        }, name='väärtus')

    pindalad = get_building_geometry_values()

    defaults = resto.get_defaults()

    data = pd.concat([ehr_andmed, andmed2, typo_andmed, defaults, pindalad])

    # Print runtime of the calculation
    # print("get_building_df() runtime: ", datetime.now() - start_time)
    return data


def convert_coordinates(x, y, dirGeoToLest=True):
    """
    Convert coordinates between global coordinates and Estonian L-EST.

    Parameters:
    - x: The X coordinate (latitude for global, L-EST X for Estonian L-EST).
    - y: The Y coordinate (longitude for global, L-EST Y for Estonian L-EST).
    - dirGeoToLest: Direction of conversion. True for Geo to L-EST, False for L-EST to Geo.

    Returns:
    A dictionary with the converted coordinates and name (if available).
    """
    # Define the URL with parameters for conversion
    url = f"{maaamet_url}geolest?x={x}&y={y}&dirGeoToLest={'true' if dirGeoToLest else 'false'}"

    try:
        # Make the GET request to the conversion service
        response = requests.get(url)
        response.raise_for_status()  # Raises an exception for 4XX/5XX errors

        # Parse the JSON response
        converted_data = response.json()

        # Return the converted coordinates
        return converted_data

    except requests.RequestException as e:
        print(f"Error during conversion: {e}")
        return None


def convert_coordinates_mass(inputData, dirGeoToLest=True):
    """
    Convert a batch of coordinates between global coordinates and Estonian L-EST.

    Parameters:
    - inputData: A list of dictionaries, each containing "nimi", "x", and "y" keys.
    - dirGeoToLest: Direction of conversion. True for Geo to L-EST, False for L-EST to Geo.

    Returns:
    A JSON response from the API with converted coordinates.
    """
    url = f"{maaamet_url}geolest"

    headers = {'Content-Type': 'application/json'}
    payload = {
        "dirGeoToLest": dirGeoToLest,
        "inputData": inputData
    }

    try:
        # Make the POST request to the conversion service with the mass query
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()  # Raises an exception for 4XX/5XX errors

        # Parse and return the JSON response
        return response.json()

    except requests.RequestException as e:
        print(f"Error during mass conversion: {e}")
        return None


def get_katastri_koordinaadid(bbox_lest):
    start_time = datetime.now()  # Start timing for feedback
    # URL to fetch data in GeoJSON format from the "kataster:ky_kehtiv" collection
    url = "https://gsavalik.envir.ee/geoserver/ogc/features/collections/kataster:ky_kehtiv/items?f=application%2Fgeo%2Bjson"

    # Optional: Specify query parameters, such as a bounding box, limit, etc.
    # Example: parameters to fetch the first 100 features (modify as needed)
    params = {
        'bbox': bbox_lest,  # '24.7,59.4,24.71,59.41', specify a bounding box (minLon,minLat,maxLon,maxLat)
        'limit': 10  # Example: limit to retrieve the first 100 features
    }

    response = requests.get(url, params=params)

    polygons = []

    if response.status_code == 200:
        collections = response.json()
        # print(collections['features'][0])
        for feature in collections['features']:
            for polygon in feature['geometry']['coordinates']:
                latlon = [{"x": lat, "y": lon} for lon, lat in polygon]
                l_est = convert_coordinates_mass(latlon)
                coordinates = [[entry["y"], entry["x"]] for entry in l_est]
                polygons.append(coordinates)
    else:
        print("Failed to fetch data, status code:", response.status_code)
        return None

    # Print runtime of the calculation
    print("get_katastri_koordinaadid() runtime: ", datetime.now() - start_time)
    return polygons


def set_nimetus_column(data):
    muutujad = get_muutujad_excel_sheet('Muutujate andmebaas')
    code_to_name_map = muutujad.set_index('Uus kood')['Nimetus'].to_dict()

    # Update 'Nimetus' column with mapping, default to index if no match is found
    data['Nimetus'] = data.index.map(lambda x: code_to_name_map.get(x, x))
    return data


def get_important_params(data):
    important_indexes = ['E1', 'E3', 'viitepunktXY', 'T1', 'energiamargis', 'ruumide_kyte', 'tarbevee_soojendamine',
                         'valgustid_seadmed_abielekter', 'ETA', 'E19', 'E20', 'E21', 'E25', 'E26', 'E27',
                         'E28', 'E29', 'E30', 'E31', 'E32', 'E33',
                         'L10', 'L11', 'L12', 'L13', 'L14', 'L15', 'L16', 'L17', 'L18',
                         'R60', 'R61', 'R62', 'R63', 'R64', 'R65', 'R66',
                         'T11', 'T12', 'T13', 'T14', 'T15', 'T16', 'T17', 'T18', 'T19', 'T20', 'T21',
                         'T22', 'T23', 'T24', 'T25', 'T26', 'T27',
                         'R17', 'R26', 'R27', 'R28', 'R29', 'R30']
    filtered_indexes = [index for index in important_indexes if index in data.index]
    important_data = data.loc[filtered_indexes]
    return important_data


def get_resto_knowledge(data):

    # To avoid duplicates creeping in, update the existing data first and then add only the new rows.
    r1tor18data = resto.calculate_R1_to_R18(data['väärtus'])
    data.update(r1tor18data)
    new_entries = r1tor18data[~r1tor18data.index.isin(data.index)]
    data = pd.concat([data, new_entries], axis=0, sort=False)

    data = data.apply(lambda col: col.apply(np.vectorize(lambda x: x.item() if isinstance(x, np.generic) else x)))

    json_data = data['väärtus'].drop('energiamargis').to_json(force_ascii=False)
    resto_data_json = get_resto_respone(json_data)

    #print(json_data)
    #print("RESTO päringu tulemus: " + str(resto_data_json))

    resto_data_df = pd.DataFrame(resto_data_json[0].values(), index=resto_data_json[0].keys()).rename(
        columns={0: 'väärtus'})
    # print(resto_data_df['väärtus'])
    data = data.combine_first(resto_data_df)
    return data


def infer(params, **kwargs):
    """Põhifunktsioon, mis loob algteadmistest uusi teadmisi hoone kohta."""
    start_time = datetime.now()  # Niisama funktsiooni ajakulu mõõtmiseks

    building_df_synd = get_building_df(get_ehr_kood(params.et_intr.aad))  # Avaandmed ja tüpoloogia teadmised
    building_df_tana = building_df_synd.copy()
    building_df_konf = building_df_synd.copy()

    # Üldkontroll, kas üldse on andmeid, mille pealt järeldusi teha.
    if building_df_synd is None:
        return "No data!"

    # Kasutajaliidese valikute lisamine DataFrame'i
    if params.et_konf.sec_pt.vs != "Muutmata":
        vs_val = params.et_konf.sec_pt.vs
        vs_df = get_kb_excel_sheet('vs')
        vs_u = float(vs_df.loc[vs_df['Nimetus'] == vs_val, 'U-arv'].iloc[0])
        building_df_konf.loc['T12', 'väärtus'] = vs_u
    if params.et_konf.sec_pt.kl != "Muutmata":
        kl_val = params.et_konf.sec_pt.kl
        kl_df = get_kb_excel_sheet('katus')
        kl_u = float(kl_df.loc[kl_df['Nimetus'] == kl_val, 'U-arv'].iloc[0])
        building_df_konf.loc['T13', 'väärtus'] = kl_u
    if params.et_konf.sec_pt.so != "Muutmata":
        so_val = params.et_konf.sec_pt.so
        so_df = get_kb_excel_sheet('sokkel')
        so_u = float(so_df.loc[so_df['Nimetus'] == so_val, 'U-arv'].iloc[0])
        building_df_konf.loc['T15', 'väärtus'] = so_u
    if params.et_konf.sec_pt.ohuleke != "Muutmata":
        ohuleke_val = params.et_konf.sec_pt.ohuleke
        ohuleke_df = get_kb_excel_sheet('õhuleke')
        ohuleke_arv = float(ohuleke_df.loc[ohuleke_df['Nimetus'] == ohuleke_val, 'Õhulekkearv'].iloc[0])
        building_df_konf.loc['T27', 'väärtus'] = ohuleke_arv

    if params.et_konf.sec_ts.vent:
        vent_val = params.et_konf.sec_ts.vent
        vent_df = get_kb_excel_sheet('ventilatsioon')
        vent_vaste = str(vent_df.loc[vent_df['Nimetus'] == vent_val, 'E31'].iloc[0])
        building_df_konf.loc['E31', 'väärtus'] = vent_vaste

    # Juhul kui tüübi kategooria on teada, siis pärime RESTO-lt uusi teadmisi.
    if building_df_synd.loc['T1', 'väärtus'] != 'Pole teada':
        # Vahetult pärast hoone ehitamist
        building_df_synd = get_resto_knowledge(building_df_synd)
        building_df_synd = set_nimetus_column(building_df_synd)  # Nimetuse col määramine 'muutujad.xlsx' faili järgi
        # Tänane olukord
        building_df_tana = get_resto_knowledge(building_df_tana)
        building_df_tana = set_nimetus_column(building_df_tana)  # Nimetuse col määramine 'muutujad.xlsx' faili järgi
        # Konfigureeritud olukord
        building_df_konf = get_resto_knowledge(building_df_konf)
        building_df_konf = set_nimetus_column(building_df_konf)  # Nimetuse col määramine 'muutujad.xlsx' faili järgi
    else:
        print("Hoone tüübi kategooria pole teada, seega RESTO funktsioonid ei käivitu.")

    print("Köetav pindala: " + str(building_df_synd['väärtus']['E21']))

    print("infer() runtime: ", datetime.now() - start_time)  # Print runtime of the calculation
    return [building_df_synd, building_df_tana, building_df_konf]

# print(get_katastri_koordinaadid(data['väärtus']['bbox_ymbrus']))


def export_infer_json(ehr_kood):
    building_df = infer(ehr_kood)
    # print("Duplicates in DataFrame: " + str(any(building_df.index.duplicated())))
    building_df = building_df[~building_df.index.duplicated(keep='first')]
    building_series = building_df['väärtus']

    json_file_path = 'G:/Downloads/eksport_naide.json'
    building_series.to_json(json_file_path, orient='index', force_ascii=False)  # This ensures UTF-8 encoding

    print(f'Data exported successfully to {json_file_path}')

def get_color_scale():
    return {
        "A": "green",
        "B": "#32CD32",  # LimeGreen
        "C": "#7FFF00",  # Chartreuse
        "D": "orange",
        "E": "#FF4500",  # OrangeRed
        "F": "red",
        "G": "#8B0000",  # DarkRed
        "H": "brown"
    }

def get_eta_varv(eta):
    # Arvud on vastavalt rekonstrueeritavate korterelamute määrusejärgsetele väärtustele
    color_scale = get_color_scale()
    if eta <= 105:
        return color_scale["A"]
    elif eta <= 125:
        return color_scale["B"]
    elif eta <= 150:
        return color_scale["C"]
    elif eta <= 180:
        return color_scale["D"]
    elif eta <= 220:
        return color_scale["E"]
    elif eta <= 280:
        return color_scale["F"]
    elif eta <= 340:
        return color_scale["G"]
    else:
        return color_scale["H"]

# print(infer(101011007))
# export_infer_json(101020350)
