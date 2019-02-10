import itertools
import math
from collections import namedtuple

import ssConstants
import components.dnSteelSection
from dnBaseLib import *

from components.node.steelConnections_EC.sceDesignData import steel_beta_w
from components.node.steelConnections_EC.sceDesignData import bolt_diameter



# bolt_props = namedtuple("BoltProps", ('a', 'b', 'c'))
# bolt_props_M8 = bolt_props(14.38, 13., 5.5)
#
# bolds_column = namedtuple("BoldsColumn", ('bold', 'number', 'offset'))
# bold_column_1 = bolds_column(bolt_props_M8, 5, 30.)

#dimension dot size
dot = 0.001
opts = {"outline": 'black', "width": 2, "tags": (soMetricCanvas.TAB_MOVE, soMetricCanvas.TAB_ROTATE, soMetricCanvas.TAB_SCALE,
                 soMetricCanvas.TAB_FIT_TO_VIEW)}

#####[srednica podkladki, szerokosc lba sruby, wysokosc lba sruby
bolt_size = {'M8': [14.38, 13., 5.5], 'M10': [18.90, 17., 7.], 'M12': [21.10, 19., 8.], 'M16': [26.75, 24., 10.],
             'M20': [33.53, 30., 13.],
             'M22': [35.72, 32., 14.], 'M24': [39.98, 36., 15.], 'M27': [45.20, 41., 17.], 'M30': [50.85, 46., 19.],
             'M36': [60.79, 55., 23.],
             'M42': [71.30, 65., 26.], 'M48': [82.60, 75., 30.]}



###OBLICZENIA###
def calc_beta_w(steel_class, fu_):
    if steel_class != 'Inna':
        beta_w = steel_beta_w[steel_class]
    else:
        beta_w = 0.35 + fu_ * 0.00125
    beta_w = min(max(beta_w, 0.8), 1.0)
    return beta_w

# srednica d0
def calc_bolt_d0(bolt_type):
    d = bolt_diameter[bolt_type][0]
    if d < 16:
        d0 = d + 1.
    elif d < 27:
        d0 = d + 2.
    else:
        d0 = d +3.
    return d0

def choose_node(beam, node):
    if beam.getNodes()[0] == node:
        binded_node = 0.
    else:
        binded_node = 1.
    return binded_node

def calc_weld_lengths(prof, alfa):
    hw = (prof['h'] - 2. * (prof['tf'] + prof['r'])) / math.cos(alfa)  # pojedyncza spoina srodnika
    lwu1 = prof['bfu']  # dluzsza spoina gornego pasa
    lwu2 = prof['bfu'] - prof['tw'] - 2. * prof['r']  # krotsza spoina gornego pasa
    lwd1 = prof['bfd']  # dluzsza spoina dolnego pasa
    lwd2 = prof['bfd'] - prof['tw'] - 2. * prof['r']  # krotsza spoina dolnego pasa
    weld_lengths = {'hw': hw, 'lwu1': lwu1, 'lwu2': lwu2, 'lwd1': lwd1, 'lwd2': lwd2}
    return weld_lengths  # {'hw': hw, 'lwu1': lwu1, 'lwu2': lwu2, 'lwd1': lwd1, 'lwd2': lwd2}

# sprawdzenie czy dlugosc pojedynczej spoiny <30mm
def check_weld_length(weld_lengths, aw):
    for i in weld_lengths:
        if weld_lengths[i] < max(6 * aw, 30):
            return False
    return True

def weld_surface(weld_lengths, weld):
    Aw = (2. * weld_lengths['hw'] + weld_lengths['lwu1'] + weld_lengths['lwu2'] + weld_lengths['lwd1'] + weld_lengths['lwd2']) * weld
    return Aw

def weld_shear_surface(weld_lengths, aw):
    return 2. * weld_lengths['hw'] * aw

# obliczenie srodka ciezkosci spoin
def weld_center(prof, welds, weld, Aw):
    e = welds['lwu1'] * weld * (prof['h'] / 2. + weld / 2.) + \
        welds['lwu2'] * weld * (prof['h'] / 2. - prof['tf'] - weld / 2.) - \
        welds['lwd1'] * weld * (prof['h'] / 2. + weld / 2.) - \
        welds['lwd2'] * weld * (prof['h'] / 2. - prof['tf'] - weld / 2.)
    e /= float(Aw)
    return e

# obliczenie momentu bezwladnosci
def mom_bezwladnosci(prof, welds, weld, e):
    Iw = welds['lwu1'] * weld ** 3. / 12. + welds['lwu1'] * weld * (prof['h'] / 2. + weld / 2. - e) ** 2. + \
         2. * weld * welds['hw'] ** 3. / 12. + 2. * welds['hw'] * weld * e ** 2. + \
         welds['lwu2'] * weld ** 3. / 12. + welds['lwu2'] * weld * (prof['h'] / 2. - prof['tf'] - weld / 2. - e) ** 2. + \
         welds['lwd1'] * weld ** 3. / 12. + welds['lwd1'] * weld * (prof['h'] / 2. + weld / 2. + e) ** 2. + \
         welds['lwd2'] * weld ** 3. / 12. + welds['lwd2'] * weld * (prof['h'] / 2. - prof['tf'] - weld / 2. + e) ** 2.
    return Iw

# obliczenie odleglosci do 4 pktow sprawdzenia
def calc_points_z(prof, welds, weld, e):
    z = [0, 0, 0, 0]
    z[0] = prof['h'] / 2. + weld / 2. - e
    z[1] = welds['hw'] / 2. - e
    z[2] = -(prof['h'] / 2. + weld / 2. + e)
    z[3] = -(welds['hw'] / 2. + e)
    return z

def calc_wsk_sprezysty(Iw, z):
    return abs(Iw / float(z))

def calc_sig_N(N, Aw):
    return N / float(Aw)

def calc_sig_M(M, Ww):
    return M / float(Ww)

def calc_tauII(V, Av):
    return abs(V/float(Av))

#maksmyalne naprezenie normalne
def calc_sig(sig_N, sig_M):
    return sig_N + sig_M

def calc_sig_pros(sig):
    return abs(sig / math.sqrt(2))

def calc_sig_pros_resistance(fu, gamma_M2):
    return 0.9 * fu / float(gamma_M2)

def calc_weld_resistance(fu, beta_w, gamma_M2):
    return fu / float(beta_w) / float(gamma_M2)

def alpha_obliczenie(m, m2, e):
    alpha_tablica = [[8.00, 8.00, 8.00, 6.90, 5.95, 5.30, 4.80, 4.50, 4.45, 4.45],
                     [8.00, 8.00, 8.00, 6.90, 5.95, 5.30, 4.80, 4.50, 4.45, 4.45],
                     [8.00, 8.00, 8.00, 6.90, 5.95, 5.30, 4.85, 4.50, 4.45, 4.45],
                     [8.00, 8.00, 8.00, 6.90, 5.95, 5.30, 4.85, 4.55, 4.45, 4.45],
                     [8.00, 8.00, 8.00, 6.90, 5.95, 5.25, 4.90, 4.55, 4.45, 4.45],
                     [8.00, 8.00, 8.00, 6.90, 5.95, 5.30, 4.90, 4.60, 4.45, 4.45],
                     [8.00, 8.00, 8.00, 6.90, 5.95, 5.35, 4.90, 4.60, 4.45, 4.45],
                     [8.00, 8.00, 8.00, 6.90, 6.00, 5.40, 4.95, 4.65, 4.45, 4.45],
                     [8.00, 8.00, 8.00, 6.90, 6.12, 5.50, 5.05, 4.70, 4.45, 4.45],
                     [8.00, 8.00, 8.00, 7.00, 6.28, 5.75, 5.25, 4.80, 4.45, 4.45],

                     [8.00, 8.00, 8.00, 7.30, 6.60, 6.05, 5, 45, 4.90, 4.50, 4.45],
                     [8.00, 8.00, 8.00, 7.90, 7.00, 6.28, 5.80, 5.25, 4.70, 4.45],
                     [8.00, 8.00, 8.00, 8.00, 8.00, 7.00, 6.28, 5.75, 5.00, 4.50],
                     [8.00, 8.00, 8.00, 8.00, 8.00, 8.00, 8.00, 6.90, 6.00, 4.90],
                     [8.00, 8.00, 8.00, 8.00, 8.00, 8.00, 8.00, 8.00, 8.00, 8.00]]
    lambda_1 = m / float(m + e)
    lambda_2 = m2 / float(m + e)
    lambda_1 = max(lambda_1, 0.001)
    lambda_1 = min(lambda_1, 0.899)
    lambda_2 = min(lambda_2, 1.399)
    lambda_2 = max(lambda_2, 0.001)
    b = 1.40
    i = 0
    x = 0
    y = 0
    c = 0
    while True:
        if lambda_2 >= b:
            x = i
            break

        else:
            b = b - 0.1
            i += 1
    i = 0
    while True:
        if lambda_1 <= c:
            y = i
            break

        else:

            c = c + 0.1
            i = i + 1

    x1 = alpha_tablica[x - 1][y - 1]
    x2 = alpha_tablica[x - 1][y]
    x3 = alpha_tablica[x][y - 1]
    x4 = alpha_tablica[x][y]
    x5 = x1 - (lambda_1 % 0.1) * (x1 - x2) / 0.1
    x6 = x3 - (lambda_1 % 0.1) * (x3 - x4) / 0.1
    alpha = x6 - (lambda_2 % 0.1) * (x6 - x5) / 0.1

    return alpha

# dlugosci efektywne blachy czolowej szeregu srub poza rozciaganym pasem
def leff_1(mx, w, e, ex, bp):
    leffcp = min(2 * math.pi * mx, math.pi * mx + w, math.pi * mx + 2 * e)
    leffnc = min(4 * mx + 1.25 * ex, e + 2 * mx + 0.625 * ex, 0.5 * bp, 0.5 * w + 2 * mx + 0.625 * ex)
    leff1 = min(leffnc, leffcp)
    leff2 = leffnc
    return {'leff1': leff1, 'leff2': leff2}

# dlugosci efektywne blachy czolowej w pierwszym szeregu srub ponizej rozciaganego pasa belki
def leff_2(m, alpha):
    leffcp = 2 * math.pi * m
    leffnc = alpha * m
    leff1 = min(leffnc, leffcp)
    leff2 = leffnc
    return {'leff1': leff1, 'leff2': leff2}

# dlugosci efektywne blachy czolowej w innym wewnetrznym szeregu srub
def leff_3(m, e):
    leffcp = 2 * math.pi * m
    leffnc = 4 * m + 1.25 * e
    leff1 = min(leffnc, leffcp)
    leff2 = leffnc
    return {'leff1': leff1, 'leff2': leff2}

# dlugosci efektywne blachy czolowej w innym skrajnym szeregu srub
def leff_4(m, e):
    leffcp = 2 * math.pi * m
    leffnc = 4 * m + 1.25 * e
    leff1 = min(leffnc, leffcp)
    leff2 = leffnc
    return {'leff1': leff1, 'leff2': leff2}

# nosnosc polki krocca teowego
def complete_yielding_of_end_plate_t_stub(bolt_in_tension_results, GAMMA_M0, fy_plate, m, emin, dw, tf, leff1,
                                          leff2,l):
    n = min(emin, 1.25 * m)
    ew = dw / 4.
    Mpl1Rd = 0.25 * leff1 * tf ** 2. * fy_plate / GAMMA_M0
    Mpl2Rd = 0.25 * leff2 * tf ** 2. * fy_plate / GAMMA_M0
    # model 1
    Ft1Rd1 = 4. * Mpl1Rd / m
    Ft1Rd2 = (8. * n - 2. * ew) * Mpl1Rd / (2. * m * n - ew * (m + n))
    Ft1Rd = min(Ft1Rd1, Ft1Rd2)
    # model 2
    Ft2Rd = (2. * Mpl2Rd + n * l * bolt_in_tension_results) / (m + n)
    # model 3
    Ft3Rd = l * bolt_in_tension_results
    FtRd = min(Ft1Rd, Ft2Rd, Ft3Rd)
    return {'n':n, 'ew':ew, 'Mpl1Rd':Mpl1Rd, 'Mpl2Rd':Mpl2Rd, 'Ft1Rd1':Ft1Rd1, 'Ft1Rd2':Ft1Rd2, 'Ft1Rd':Ft1Rd, 'Ft2Rd':Ft2Rd, 'Ft3Rd':Ft3Rd, 'FtRd':FtRd,'leff1':leff1, 'leff2':leff2}

# nosnosc srodnika belki w strefie rozciaganej
def srodnik_belki_rozciaganie(beff_t_wb, twb, fy_wb, GAMMA_M0):
    Ft_wb_Rd = beff_t_wb * twb * fy_wb / float(GAMMA_M0)
    return Ft_wb_Rd

# panel srodnika slupa
def panel_srodnika_scinanie(Avc_column, fy_slupa, GAMMA_M0):
    nosnosc_na_scinanie = 0.9 * fy_slupa * Avc_column / 3. ** 0.5 / GAMMA_M0
    return  nosnosc_na_scinanie

# wspolczynnik_redukcyjny_interakcja_ze_scinaniem
def obliczenie_wspolczynnika_redukcyjnego_interakcji_ze_scinaniem(beff_c_wc, t_wc, przekroj_czynny_slupa):
    wspolczynnik_redukcyjny_interakcja_ze_scinaniem = 1. / (1. + 1.3 * (
        beff_c_wc * t_wc / przekroj_czynny_slupa) ** 2.) ** 0.5
    return wspolczynnik_redukcyjny_interakcja_ze_scinaniem

# wspolczynnik_kwc
def wspolczynnik_redukcyjny_kwc(max_naprezenie_normalne, fy_slupa):
    if max_naprezenie_normalne <= 0.7 * fy_slupa:
        wspolczynnik_kwc = 1.
    else:
        wspolczynnik_kwc = 1.7 - max_naprezenie_normalne / float(fy_slupa)
    return wspolczynnik_kwc

# beff_c_wc
def szerokosc_efektywna_srodnika_slupa_przy_sciskaniu(tp, c, tfb, ap, tfc, s):
    sp = min(tp + c, 2. * tp)
    beff_c_wc = tfb + 2. * 2. ** 0.5 * ap + 5. * (tfc + s) + sp
    return beff_c_wc

# wspolczynnik_wyboczenia
def obliczenie_wspolczynnika_wyboczenia(beff_c_wc, tfc, rc, hc, fy_wc, E, twc):
    dwc = hc - 2 * (tfc + rc)
    smuklosc_plytowa = 0.932 * (beff_c_wc * dwc * fy_wc / E / twc ** 2) ** 0.5
    if smuklosc_plytowa <= 0.72:
        wspolczynnik_wyboczenia = 1.
    else:
        wspolczynnik_wyboczenia = (smuklosc_plytowa - 0.2) / smuklosc_plytowa ** 2.
    return wspolczynnik_wyboczenia

# srodnik slupa przy poprzecznym sciskaniu
def srodnik_przy_sciskaniu(wspolczynnik_redukcyjny_interakcja_ze_scinaniem, wspolczynnik_kwc, beff_c_wc, t_wc, fy_slupa,
                           GAMMA_M0, GAMMA_M1, wspolczynnik_wyboczenia):
    nosnosc_srodnika_na_sciskanie1 = wspolczynnik_redukcyjny_interakcja_ze_scinaniem * wspolczynnik_kwc * beff_c_wc * t_wc * fy_slupa / float(GAMMA_M0)
    nosnosc_srodnika_na_sciskanie2 = wspolczynnik_redukcyjny_interakcja_ze_scinaniem * wspolczynnik_wyboczenia * wspolczynnik_kwc * beff_c_wc * t_wc * fy_slupa / float(GAMMA_M1)
    nosnosc_srodnika_na_sciskanie = min(nosnosc_srodnika_na_sciskanie1, nosnosc_srodnika_na_sciskanie2)
    return nosnosc_srodnika_na_sciskanie

#Nosnosc belki na zginanie
def nosnosc_na_zginanie(Wpl, fy, GAMMA_M0):
    Mc_Rd=Wpl*fy/GAMMA_M0
    return Mc_Rd

#nosnosc pasa i srodnika belki przy sciskaniu
def pas_i_srodnik_przy_sciskaniu(Mc_Rd, h_belki, tfb):
    Fc_fb_Rd=Mc_Rd/(h_belki-tfb)
    return Fc_fb_Rd

# srodnik slupa przy poprzecznym rozciaganiu
def srodnik_przy_rozciaganiu(wspolczynnik_redukcyjny_interakcja_ze_scinaniem, beff_t_wc, t_wc, fy_slupa, GAMMA_M0):
    nosnosc_srodnika_na_rozciaganie = wspolczynnik_redukcyjny_interakcja_ze_scinaniem * beff_t_wc * t_wc * fy_slupa / (GAMMA_M0)
    return  nosnosc_srodnika_na_rozciaganie

# dlugosci efektywne nieuzebrowanego pasa wewnetrznego szeregu srub
def leff_5(m, e):
    leffcp = 2. * math.pi * m
    leffnc = 4. * m + 1.25 * e
    leff1 = min(leffnc, leffcp)
    leff2 = leffnc
    return {'leff1': leff1, 'leff2': leff2}

# dlugosci efektywne nieuzebrowanego pasa w skrajnym szeregu srub
def leff_6(m, e, e1):
    leffcp = min(2. * math.pi * m, math.pi * m + 2. * e1)
    leffnc = min(4. * m + 1.25 * e, 2. * m + 0.625 * e + e1)
    leff1 = min(leffnc, leffcp)
    leff2 = leffnc
    return {'leff1': leff1, 'leff2': leff2}

# scinanie sruby
def bolt_in_shear(is_threaded, bolt_diameter, bolt_tensile_area, bolt_class, fu_bolt, GAMMA_M2):
    if is_threaded == 0:
        alpha_v = 0.6
        bolt_area = math.pi * bolt_diameter * bolt_diameter / 4.
    else:
        if bolt_class == '4.6' or bolt_class == '5.6' or bolt_class == '8.8':
            alpha_v = 0.6
        else:
            alpha_v = 0.5
        bolt_area = bolt_tensile_area
    bolt_shear_resistance = ((alpha_v * fu_bolt * bolt_area) / GAMMA_M2)
    return {'bolt_shear_resistance': bolt_shear_resistance, 'alpha_v': alpha_v, 'bolt_area': bolt_area,
            'is_threaded': is_threaded, 'bolt_class': bolt_class, 'bolt_tensile_area': bolt_tensile_area}

# rozciaganie i przeciagniecie sruby
def bolt_in_tension(fu_bolt, fu_plate, bolt_tensile_area, GAMMA_M2, bolt_type, plate_thickness):
    bolt_tension_resistance = ((0.9 * fu_bolt * bolt_tensile_area) / GAMMA_M2)
    factor_dm = (bolt_size[bolt_type][0] + bolt_size[bolt_type][1]) / 2.

    plate_tension_resistance = ((0.6 * math.pi * factor_dm * plate_thickness * fu_plate) / GAMMA_M2)
    return {'bolt_tension_resistance': bolt_tension_resistance, 'plate_tension_resistance': plate_tension_resistance,
            'factor_dm': factor_dm, 'bolt_tensile_area': bolt_tensile_area, 'E': bolt_size[bolt_type][0],
            'S': bolt_size[bolt_type][1]}

# docisk sruby
def bolt_bearing(distance_e1, distance_e2, bolt_diameter, bolt_diameter0, plate_thickness, GAMMA_M2, fu_bolt, fu_plate):
    alpha_b = min((distance_e1 / (3. * bolt_diameter0)), fu_bolt / fu_plate, 1.0)
    factor_k1 = min(((2.8 * distance_e2 / bolt_diameter0) - 1.7), 2.5)
    bolt_bearing_resistance = (
        (

            factor_k1 * alpha_b * fu_plate * bolt_diameter * plate_thickness) / GAMMA_M2)
    return {'bolt_bearing_resistance': bolt_bearing_resistance, 'alpha_b': alpha_b, 'factor_k1': factor_k1}

# docisk sruby posrednie
def bolt_bearing2(distance_p1, distance_e2, bolt_diameter, bolt_diameter0, plate_thickness, GAMMA_M2, fu_bolt, fu_plate):
    alpha_b = min(((distance_p1 / (3. * bolt_diameter0))-1/4), fu_bolt / fu_plate, 1.0)
    factor_k1 = min(((2.8 * distance_e2 / bolt_diameter0) - 1.7), 2.5)
    bolt_bearing_resistance = (
        (

            factor_k1 * alpha_b * fu_plate * bolt_diameter * plate_thickness) / GAMMA_M2)
    return {'bolt_bearing_resistance': bolt_bearing_resistance, 'alpha_b': alpha_b, 'factor_k1': factor_k1}

def calc_welds(prof, alfa, aw, NEd, VEd, MEd):
    weld_lengths = calc_weld_lengths(prof, alfa)
    Aw = weld_surface(weld_lengths, aw)
    Av = weld_shear_surface(weld_lengths, aw)
    e = weld_center(prof, weld_lengths, aw, Aw)
    Iw = mom_bezwladnosci(prof, weld_lengths, aw, e)
    points_z = calc_points_z(prof, weld_lengths, aw, e)
    sig_N = calc_sig_N(NEd, Aw)
    tauII = calc_tauII(VEd, Av)
    weld_sigmas = []
    for z in points_z:
        Ww = calc_wsk_sprezysty(Iw, z)
        sig_M = calc_sig_M(MEd, Ww)
        sig = calc_sig(sig_N, sig_M)
        sig_pros = calc_sig_pros(sig)
        weld_sigmas.append([z, sig_pros])
    max_sigma = max(weld_sigmas, key=lambda item: item[1])
    return {'tauII': tauII, 'z': max_sigma[0], 'sig_pros': max_sigma[1], 'Aw': Aw, 'Av': Av}

def check_which_is_column(node,):
    angle = node.getElements(node='both')[0].getAngle()
    angle2 = node.getElements(node='both')[1].getAngle()
    which_column = 1
    if 1.5700 < angle < 1.571 or 4.7120 < angle < 4.7128:
        which_column = 1
    elif 1.5700 < angle2 < 1.571 or 4.7120 < angle2 < 4.7128:
        which_column = 0
    return which_column

def check_if_column_on_right_side(node, which_column):
    coords_beam = node.getElements(node='both')[1-which_column].getCoords()
    coords_column = node.getElements(node='both')[which_column].getCoords()
    if round(coords_column[0],4) == round(coords_beam[0],4):
        column_is_on_right = 0
    else:
        column_is_on_right = 1
    if coords_beam[0] > coords_beam[2]:     #belka jest obrocona
        column_is_on_right = 1 - column_is_on_right
    return column_is_on_right



### POBIERANIE DANYCH Z PROGRAMU ###
def get_profile_parameters(node_object, i):
    element = node_object.getElements(node='both')[i]
    profile = element.getComplexProfile().getProfiles()[0].getSection()
    element_material = element.getComplexProfile().getPrincipalMaterial().getDesignData(profile,
                                                                                        standard=soConstants.EUROCODE_STANDARD)
    __cOrdCpObj__edge_list = element.getComplexProfile().getEdgeList()
    fy = element_material['fy']
    fu = element_material['fu']
    prof_type = profile.getType()
    h = profile.get_H()
    tf = profile.get_t()
    r = profile.get_r()
    bfu = profile.get_S()
    bfd = profile.get_S1()
    tw = profile.get_g()
    A = profile.get_A() * 100.  #mm2
    wpl = components.dnSteelSection.calculate_resistant_factor(__cOrdCpObj__edge_list, 0)['W']
    return {'A': A, 'h': h, 'tf': tf, 'r': r, 'bfu': bfu, 'bfd': bfd, 'tw': tw, 'type': prof_type, 'fu': fu, 'fy': fy, 'wpl': wpl}



### SPRAWDZANIE BLEDOW ###
def check_elements_number(node_object):
    elements = node_object.getElements(node='both')
    return len(elements) == 2

# sprawdzenie typu profilu
def check_profile(node_object):
    element = node_object.getElements(node='both')
    check1 = element[0].getComplexProfile().getProfiles()[0].getSection().getType()
    check2 = element[1].getComplexProfile().getProfiles()[0].getSection().getType()
    return check1 is ssConstants.I_BEAM and check2 is ssConstants.I_BEAM

def check_profiles_same(node_object):
    element = node_object.getElements(node='both')
    beam1 = element[0].getComplexProfile().getProfiles()[0].getSection()
    beam2 = element[1].getComplexProfile().getProfiles()[0].getSection()
    return beam1 == beam2

# sprawdzenie czy spoina pachwinowa nie wychodzi poza blache
def check_is_weld_out_plate(above, under, aw, m1, m2, e1, e2):
    if not above:
        e1 = 0
    if not under:
        e2 = 0
    aw *= 1.5
    return aw < m1+e1 and aw < m2+e2

#sprawdzenie czy jest minimum 2 rzedy srub
def check_is_min2_rows(is_above, is_under, rows_up, rows_down):
    return (is_above + is_under + rows_up + rows_down) >= 2

# warunek sprawdzajacy odleglosc spoiny od lba sruby
def check_weld_bolt_distance(m1m2, aw, bolt_type):
    return (m1m2 - aw - 0.5 * bolt_size[bolt_type][1]) > 5.

# sprawdzenie warunku odleglosci e
def check_tw_e(e, l1, bolt_type, aw, bf, tw):
    D = bolt_size[bolt_type][1]
    return (e - l1 + 0.5*D) < (0.5 * bf - 0.5 * tw - aw - 5.)

def check_max_e(e, tp):
    return e < 4 * tp + 40.

def check_min_e(e, bolt_type):
    return e > 1.2 * calc_bolt_d0(bolt_type)

def check_min_e1e2(e1e2, bolt_type):
    return e1e2 > 1.2 * calc_bolt_d0(bolt_type)

def check_max_e1e2(e1e2, tp):
    return e1e2 < 4 * tp + 40.

def check_min_p1p3(p1p3, aw, bolt_type):
    return (p1p3 - aw - 0.5 * bolt_size[bolt_type][1]) > 5.

def check_min_p2p4(p2p4, bolt_type):
    return p2p4 > 2.4 * calc_bolt_d0(bolt_type)

def check_max_p2p4(p2p4, tp):
    return p2p4 < min(14 * tp, 200.)

def check_dist_between_up_down_rows(p1, p2, p3, p4, H, tf, rows_up, rows_down, bolt_type):
    return (H - 2 * tf - p1 - (rows_up-1)*p2 - p3 - (rows_down-1)*p4) > 2.4 * calc_bolt_d0(bolt_type)

# sprawdzenie kata nachylenia belek
def check_beams_angle(node, is_column, which_column):
    angle = node.getElements(node='both')[1-which_column].getAngle()        #belka
    angle2 = node.getElements(node='both')[which_column].getAngle()         #slup/belka
    pi = 3.14159265358
    r1 = abs(round(angle%pi, 4))
    r2 = abs(round(angle2%pi, 4))
    if not is_column:
        return r1 == 1.5708 and r2 == 1.5708
    else:
        return r1 == 1.5708 and r2 == 0.



### RYSOWANIE ###
def get_draw_results(node, which_column):
    element1 = node.getElements(node='both')[1-which_column]    #beam
    element2 = node.getElements(node='both')[which_column]      #column/beam
    coords = element1.getComplexProfile().getEdgeList()
    profile_length1 = element1.getLength() * 1000.
    profile_length2 = element2.getLength() * 1000.
    side_coords1 = element1.getComplexProfile().getCoordsForSideView(adjustType=0)
    side_coords2 = element2.getComplexProfile().getCoordsForSideView(adjustType=0)
    profile_coords = coords[0]

    return {'profile_coords': profile_coords, 'side_coords1': side_coords1, 'profile_length1': profile_length1,
            'side_coords2': side_coords2, 'profile_length2': profile_length2}

def draw_boundary(canvas, x, y):
    z = 10.
    exterior_boundary_tags = (soMetricCanvas.TAB_EXTERIOR_BOUNDARY, soMetricCanvas.TAB_FIT_TO_VIEW)
    canvas.create_polygon(
        -0.5 * x - z, -0.5 * y - z, -0.5 * x - z, 0.5 * y + z, 0.5 * x + z, 0.5 * y + z, 0.5 * x + z, -0.5 * y - z,
        width=5,
        fill='',
        tags=exterior_boundary_tags)

def draw_bolt(canvas, x, y, diameter):
    canvas.create_polygon(x - diameter / 2., y, x - diameter / 4., diameter / 2. + y, x + diameter / 4.,
                          diameter / 2. + y,
                          x + diameter / 2., y, x + diameter / 4., - diameter / 2. + y, x - diameter / 4.,
                          - diameter / 2. + y,
                          fill='grey', **opts)

def draw_side_bolt(canvas, y, diameter, bolt_type, plate_thickness, tf_c):
    canvas.create_rectangle(tf_c, 0.5 * diameter + y, tf_c + bolt_size[bolt_type][2],
                            0.25 * diameter + y,
                            fill='grey', **opts)
    canvas.create_rectangle(tf_c, 0.25 * diameter + y, tf_c + bolt_size[bolt_type][2],
                            -0.25 * diameter + y,
                            fill='grey', **opts)
    canvas.create_rectangle(tf_c, -0.25 * diameter + y, tf_c + bolt_size[bolt_type][2],
                            -0.5 * diameter + y,
                            fill='grey', **opts)
    canvas.create_rectangle(-plate_thickness, 0.5 * diameter + y, -plate_thickness - bolt_size[bolt_type][2],
                            0.25 * diameter + y,
                            fill='grey', **opts)
    canvas.create_rectangle(-plate_thickness, 0.25 * diameter + y, -plate_thickness - bolt_size[bolt_type][2],
                            -0.25 * diameter + y,
                            fill='grey', **opts)
    canvas.create_rectangle(-plate_thickness, -0.25 * diameter + y, -plate_thickness - bolt_size[bolt_type][2],
                            -0.5 * diameter + y,
                            fill='grey', **opts)
    canvas.create_rectangle(-plate_thickness - bolt_size[bolt_type][2], 0.3 * diameter + y,
                            -plate_thickness - bolt_size[bolt_type][2] - 0.3 * diameter,
                            -0.3 * diameter + y,
                            fill='grey', **opts)

def draw_plate(canvas, dis, bf, H):
    canvas.create_rectangle(-0.5 * bf - dis['l1'], -0.5 * H - dis['m2'] - dis['e2'],
                            0.5 * bf + dis['l1'], 0.5 * H + dis['m1'] + dis['e1'],
                            fill='#a59151', **opts)

def draw_profile(canvas, list1):
    coords = []
    for c in list1:
        coords += c
    canvas.create_polygon(*coords, fill='#fddd79', **opts)

def bolt_grid_setup(canvas, rows_u,rows_d, dis, prof, bolt_diameter, is_above, is_under):
    xi=[]
    xi.append(-0.5 * prof['bfu'] - dis['l1'] + dis['e'])
    xi.append(0.5 * prof['bfu'] + dis['l1'] - dis['e'])
    for x in xi:
        if is_above:
            y = 0.5 * prof['h'] + dis['m1']
            draw_bolt(canvas, x, y, bolt_diameter)
        if is_under:
            y = -0.5 * prof['h'] -dis['m2']
            draw_bolt(canvas, x, y, bolt_diameter)
        for row_num in range(int(rows_u)):
            y = 0.5*prof['h'] - prof['tf'] - dis['p1'] - row_num * dis['p2']
            draw_bolt(canvas, x, y, bolt_diameter)
        for row_num in range(int(rows_d)):
            y = -0.5*prof['h'] + prof['tf'] + dis['p3'] + row_num * dis['p4']
            draw_bolt(canvas, x, y, bolt_diameter)

def bolt_side_grid_setup(canvas, rows_u, rows_d, dis, d, bolt, tp, H, tf, is_above, is_under, is_column, tf_c):
    if not is_column:
        tf_c=tp
    if is_above:
        y = 0.5 * H + dis['m1']
        draw_side_bolt(canvas, y, d, bolt, tp, tf_c)
    if is_under:
        y = -0.5 * H - dis['m2']
        draw_side_bolt(canvas, y, d, bolt, tp, tf_c)
    for row_num in range(int(rows_u)):
        y = 0.5 * H - tf - dis['p1'] - row_num * dis['p2']
        draw_side_bolt(canvas, y, d, bolt, tp, tf_c)
    for row_num in range(int(rows_d)):
        y = -0.5 * H + tf + dis['p3'] + row_num * dis['p4']
        draw_side_bolt(canvas, y, d, bolt, tp, tf_c)

def draw_horizontal_dimension(canvas, plate, dis, H):
    y1 = 0.5 * H + dis['m1'] + dis['e1']
    y2 = -0.5 * H - dis['m2'] - dis['e2']
    canvas.draw_dimension(-0.5 * plate['lp'], y1, -0.5 * plate['lp']+dis['e'], y1, 10, u'e',
                          end_dot_size=dot)
    if not dis['l1'] < 0.01:
        canvas.draw_dimension(0.5 * plate['lp'] - dis['l1'], y1, 0.5 * plate['lp'], y1, 10, u'l\u2081', end_dot_size=dot)
    canvas.draw_dimension(-0.5 * plate['lp'], y2, 0.5 * plate['lp'], y2, -20, u'l\u209A',
                          end_dot_size=dot)

def draw_horizontal_side_dimension(canvas, H, m2, e2, tp):
    canvas.draw_dimension(0, -0.5 * H - m2 - e2, -tp, -0.5 * H - m2 - e2, 25, u't\u209A', end_dot_size=dot)

def draw_vertical_dimension(canvas, width, dis, tf, H):
    x = -0.5 * width
    canvas.draw_dimension(-x, -0.5 * H - dis['m2'] - dis['e2'], -x, 0.5 * H + dis['m1'] + dis['e1'], -25, u'h\u209A',
                          end_dot_size=dot)
    if not dis['m1'] < 0.01:
        canvas.draw_dimension(x, 0.5 * H, x, 0.5 * H + dis['m1'], 10, u'm\u2081', end_dot_size=dot)
    if not dis['m2'] < 0.01:
        canvas.draw_dimension(x, -0.5 * H - dis['m2'], x, -0.5 * H, 10, u'm\u2082', end_dot_size=dot)
    if not dis['e1'] < 0.01:
        canvas.draw_dimension(x, 0.5 * H + dis['m1'], x, 0.5 * H + dis['m1'] + dis['e1'], 10, u'e\u2081', end_dot_size=dot)
    if not dis['e2'] < 0.01:
        canvas.draw_dimension(x, -0.5 * H - dis['m2'] - dis['e2'], x, -0.5 * H - dis['m2'], 10, u'e\u2082', end_dot_size=dot)
    if not dis['p1'] < 0.01:
        canvas.draw_dimension(x, 0.5 * H - tf - dis['p1'], x, 0.5 * H - tf, 10, u'p\u2081', end_dot_size=dot)
    if not dis['p2'] < 0.01:
        canvas.draw_dimension(x, 0.5 * H - tf - dis['p1'] - dis['p2'], x, 0.5 * H - tf - dis['p1'], 10, u'p\u2082', end_dot_size=dot)
    if not dis['p3'] < 0.01:
        canvas.draw_dimension(x, -0.5 * H + tf, x, -0.5 * H + tf + dis['p3'], 10, u'p\u2083', end_dot_size=dot)
    if not dis['p4'] < 0.01:
        canvas.draw_dimension(x, -0.5 * H + tf + dis['p3'], x, -0.5 * H + tf + dis['p3'] + dis['p4'], 10, u'p\u2084', end_dot_size=dot)

def transformCoords(delta_x, realCoordX, realCoordY):
    x = realCoordX + delta_x
    y = -realCoordY
    return [x, y]

def draw_side_profile(canvas, delta_x, list1, length):
    for iplInfo in list1:
        cs = []
        for pIndex in iplInfo['planesMaxXOrder']:
            c = iplInfo['planes'][pIndex]
            ec = (0., 0., length, 0.)
            c1 = transformCoords(delta_x, ec[0], ec[1] + c[1])
            c2 = transformCoords(delta_x, ec[0], ec[1] + c[3])
            c3 = transformCoords(delta_x, ec[2], ec[3] + c[1])
            c4 = transformCoords(delta_x, ec[2], ec[3] + c[3])
            coords = [c1[0], c1[1], c3[0], c3[1]] + [c4[0], c4[1], c2[0], c2[1]]
            cs += coords
        canvas.create_polygon(*cs, fill='#fddd79', **opts)

def draw_side_column(canvas, list1, length, h):
    for iplInfo in list1:
        cs = []
        for pIndex in iplInfo['planesMaxXOrder']:
            c = iplInfo['planes'][pIndex]
            ec = (h/2, -length/2, h/2, length/2)
            c1 = [ec[0]-c[1], ec[1]]
            c2 = [ec[2]-c[1], ec[3]]
            c3 = [ec[2]-c[3], ec[3]]
            c4 = [ec[0]-c[3], ec[1]]
            coords = [c1[0], c1[1], c2[0], c2[1]] + [c3[0], c3[1], c4[0], c4[1]]
            cs += coords
        canvas.create_polygon(*cs, fill='#fddd79', **opts)

def draw_side_plate(canvas,dist, H, tp):
    canvas.create_rectangle(0, 0.5 * H + dist['m1'] + dist['e1'], tp, -0.5 * H - dist['m2'] - dist['e2'],
                            fill='#a59151', **opts)

def draw_side_welds(canvas, H, tf, r, tp, aw, is_column):
    aw *= 1.5
    canvas.create_polygon(-tp, 0.5 * H, -tp, 0.5 * H + aw, -tp - aw, 0.5 * H,
                          fill='grey', **opts)
    canvas.create_polygon(-tp, 0.5 * H - tf, -tp, 0.5 * H - tf - aw, -tp - aw, 0.5 * H - tf,
                          fill='grey', **opts)
    canvas.create_rectangle(-tp, 0.5 * H - tf - r, -tp - aw, -0.5 * H + tf + r,
                            fill='grey', **opts)
    canvas.create_polygon(-tp, -0.5 * H + tf, -tp, -0.5 * H + tf + aw, -tp - aw, -0.5 * H + tf,
                          fill='grey', **opts)
    canvas.create_polygon(-tp, -0.5 * H, -tp, -0.5 * H - aw, -tp - aw, -0.5 * H,
                          fill = 'grey', **opts)

    if not is_column:
        canvas.create_polygon(tp, 0.5 * H, tp, 0.5 * H + aw, tp + aw, 0.5 * H,
                              fill='grey', **opts)
        canvas.create_polygon(tp, 0.5 * H - tf, tp, 0.5 * H - tf - aw, tp + aw, 0.5 * H - tf,
                              fill='grey', **opts)
        canvas.create_rectangle(tp, 0.5 * H - tf - r, tp + aw, -0.5 * H + tf + r,
                                fill='grey', **opts)
        canvas.create_polygon(tp, -0.5 * H + tf, tp, -0.5 * H + tf + aw, tp + aw, -0.5 * H + tf,
                              fill='grey', **opts)
        canvas.create_polygon(tp, -0.5 * H, tp, -0.5 * H - aw, tp + aw, -0.5 * H,
                              fill='grey', **opts)

def draw_welds(canvas, prof, aw):
    h=prof['h']
    bf = prof['bfu']
    r = prof['r']
    tf = prof['tf']
    tw = prof['tw']
    aw *= 1.5
    # gorny pas
    canvas.create_rectangle(-0.5 * bf, 0.5 * h + aw,
                            0.5 * bf, 0.5 * h,
                            fill='grey', **opts)
    canvas.create_rectangle(-0.5 * bf, 0.5 * h - tf,
                            -0.5 * tw - r, 0.5 * h - tf - aw,
                            fill='grey', **opts)
    canvas.create_rectangle(0.5 * tw + r, 0.5 * h - tf,
                            0.5 * bf, 0.5 * h - tf - aw,
                            fill='grey', **opts)
    #srodnik
    canvas.create_rectangle(-0.5 * tw - aw, 0.5 * h - tf - r,
                            -0.5 * tw, - 0.5 * h + tf + r,
                            fill='grey', **opts)
    canvas.create_rectangle(0.5 * tw, 0.5 * h - tf - r,
                            0.5 * tw + aw, - 0.5 * h + tf + r,
                            fill='grey', **opts)
    # dolny pas
    canvas.create_rectangle(-0.5 * bf, -0.5 * h - aw,
                            0.5 * bf, -0.5 * h,
                            fill='grey', **opts)
    canvas.create_rectangle(-0.5 * bf, -0.5 * h + tf,
                            -0.5 * tw - r, -0.5 * h + tf + aw,
                            fill='grey', **opts)
    canvas.create_rectangle(0.5 * tw + r, -0.5 * h + tf,
                            0.5 * bf, -0.5 * h + tf + aw,
                            fill='grey', **opts)

