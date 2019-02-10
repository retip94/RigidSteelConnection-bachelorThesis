# -*- coding: cp1250 -*-

"""
plik: dnRigidBeam.py
"""
# import sys
#
# root = sys.path[3]
# sys.path.insert(1, root + '\\library.zip')
# sys.path.insert(1, root + '\\Design\\lib')
# sys.path.insert(1, root + '\\Design\\lib\\components')

# here you import all modules you need
# general
from dnBaseLib import *

# python modules
import os
import copy

# design modules
import dnConstants
import dnComponent
import dnComponentDlg

# soldis
import sdConstants
import sdRTFReport

# this is module of special interest - look up the file for steel connections funcionality
import dnRigidBeamLib
from dnRigidBeamLib import *

import soTranslator
import PyRTF
from Tkinter import *


def trans(exp):
    import dnRigidBeam_EN
    return soTranslator.trans(exp, {
        soConstants.ENGLISH: dnRigidBeam_EN.data,
    })


# some helpful functions
from components.node.steelConnections_EC.sceDesignData import get_steel_strength_EN
from components.node.steelConnections_EC.sceDesignData import get_steel_strength_EN_names
from components.node.steelConnections_EC.sceDesignData import bolt_strength
from components.node.steelConnections_EC.sceDesignData import bolt_diameter
from components.node.steelConnections_EC.sceDesignData import get_gamma


'''
def trans(exp):
    import PipeSpliceConnection_EN
    return soTranslator.trans(exp, {
        soConstants.ENGLISH: PipeSpliceConnection_EN.data,
    })
'''

# CONSTANTS

# HERE DEFINE DESIGN SUBJECTS
EXTREMAL_SHEAR_RATIO = trans(u'Ścinanie')
EXTREMAL_BENDING_RATIO = trans(u'Zginanie')
EXTREMAL_TENSION_RATIO = trans(u'Rozciąganie')
EXTREMAL_BENDING_TENSION_RATIO = trans(u'Zginanie z rociąganiem')
EXTREMAL_COLUMN_SHEAR_RATIO = trans(u'Ścięcie środnika')
EXTREMAL_WELD_RATIO = trans(u'Naprężenia wypadkowe spoin')
EXTREMAL_WELD2_RATIO = trans(u'Naprężenia prostopadłe spoin')


# this are some helpful functions too
def merge_dict(x, y):
    '''Given two dicts, merge them into a new dict as a shallow copy.'''
    z = x.copy()
    z.update(y)
    return z



def find_extremum(comb_data_list, force):
    _min_data, _max_data = None, None
    for comb_data in comb_data_list:
        if _min_data is None or comb_data['section_forces'][force] < _min_data['section_forces'][force]:
            _min_data = comb_data
        if _max_data is None or comb_data['section_forces'][force] > _max_data['section_forces'][force]:
            _max_data = comb_data
    return _min_data, _max_data


def results_dict(data):
    results = {}
    results['comb_name'] = data['name']
    comb_data = {}
    comb_data['section_forces'] = {'Ned': data['section_forces']['N'],
                                   'Ved': data['section_forces']['Tz'],
                                   'Med': data['section_forces']['My']}
    results['load_groups'] = data['load_groups']
    results['comb_data'] = comb_data
    return results


def _max_comb_condition(results, condition):
    max = None
    data_comb = None
    for data in results:
        ratio = results[data][1]['ratio'][condition]
        if ratio >= max:
            max = ratio
            data_comb = results[data][0]['data']
    return {'data': data_comb, 'ratio': max}


# this is your main dlg class
class RigidBeamConnectionDlg(dnComponentDlg.ComponentContextNodeDlg):
    controlWidth = 12

    def __init__(self, parent, compObj, **kw):

        # init base class
        dnComponentDlg.ComponentContextNodeDlg.__init__(self, parent, compObj, **kw)

        # register tabs
        # to register tab you need to provide its create and update functions
        self.registerTab('results_joint',
                         image=self._createImage('detailed_results_icon.png'),
                         disableImage=self._createImage('detailed_results_icon_disabled.png'),
                         createFunc=self.createTab_results,
                         updateFun=self.updateTab_results,
                         subjectId=1)

        # permanent panel will be always visible on the right side of window
        self.registerPermamentPanel(createFun=self.createPermanentPanel, updateFun=self.updatePermanentPanel)

        # some additional buttons
        self.registerCalcSavingOptButton()
        self.registerRaportGeneratorButton()

        # set your only tab as the default one
        self.setDefaultTab('results_joint')

        # this builds the window according to tabs you registered
        self.build()

    def setVars(self):

        # all you add here must be defined in Component.setDefault function, this vars are accesible in both
        # component and dlg
        # these can be for example steel f_u, that you want to be passed by user and that will be used for your component
        self.addVar('thickness_plate', type='IntVar')
        self.addVar('fy_plate', type='DoubleVar')
        self.addVar('fu_plate', type='DoubleVar')
        self.addVar('selected_steel', type='StringVar')
        self.addVar('joint_category', type='StringVar')
        self.addVar('bolt_type', type='StringVar')
        self.addVar('bolt_class', type='StringVar')
        self.addVar('is_threaded', type='IntVar')
        self.addVar('bolts_above', type='IntVar')
        self.addVar('weld_type', type='StringVar')
        self.addVar('aw', type='DoubleVar')
        self.addVar('bolt_type', type='StringVar')
        self.addVar('bolt_class', type='StringVar')
        self.addVar('is_threaded', type='IntVar')
        self.addVar('bolts_above', type='IntVar')
        self.addVar('dis_e1', type='DoubleVar')
        self.addVar('bolts_under', type='IntVar')
        self.addVar('dis_e2', type='DoubleVar')
        self.addVar('dis_m1', type='DoubleVar')
        self.addVar('dis_m2', type='DoubleVar')
        self.addVar('dis_e', type='DoubleVar')
        self.addVar('dis_l1', type='DoubleVar')
        self.addVar('dis_p1', type='DoubleVar')
        self.addVar('dis_p2', type='DoubleVar')
        self.addVar('rows_up', type='IntVar')
        self.addVar('rows_down', type='IntVar')
        self.addVar('dis_p3', type='DoubleVar')
        self.addVar('dis_p4', type='DoubleVar')
        self.addVar('column_on_right', type='IntVar')
        self.addVar('dis_s1', type='DoubleVar')
        self.addVar('dis_s2', type='DoubleVar')

    # this is some helpful function ;)
    def find_the_worst(self, res_data):
        max_ratio = 0.
        max_ratio_data = None

        for comb_name, comb_data in res_data.items():
            r = comb_data['ratio']
            if r >= max_ratio:
                max_ratio = r
                max_ratio_data = comb_data
                max_ratio_comb_name = comb_name

        return max_ratio_data, max_ratio_comb_name

    # create side panel
    def createPermanentPanel(self, parent):

        # main frame to hold all content of panel
        joint_frame = soFrame(parent)
        joint_frame.pack()

        # region canvas
        # the notebook is a little frame with tabs you can register
        canvas_notebook = soNoteBook(joint_frame)
        canvas_notebook.grid(row=0, column=0, sticky=S + N + W + E, padx=0, pady=0)
        # first frame
        canvas_scheme_1_tab = soFrame(canvas_notebook)
        canvas_notebook.add(canvas_scheme_1_tab, text=trans(u'Przekrój'))
        # second frame
        canvas_scheme_2_tab = soFrame(canvas_notebook)
        canvas_notebook.add(canvas_scheme_2_tab, text=trans(u'Widok'))

        # you need to create canvas for each tab, even though only one is visible at a time
        cC1_size = 207, 207
        self.cC1 = soMetricCanvas(canvas_scheme_1_tab, width=cC1_size[0], height=cC1_size[1], bg='white', bd=2,
                                  relief=GROOVE)
        self.cC1.grid(row=0, column=0, sticky=S + N + W + E, padx=3, pady=3)

        self.cC2 = soMetricCanvas(canvas_scheme_2_tab, width=cC1_size[0], height=cC1_size[1], bg='white', bd=2,
                                  relief=GROOVE)
        self.cC2.grid(row=0, column=0, sticky=S + N + W + E, padx=3, pady=3)
        # endregion
        # region parameters
        parameters_notebook = soNoteBook(joint_frame, width=cC1_size[0])
        parameters_notebook.grid(row=1, column=0, sticky=S + N + W + E, padx=0, pady=0)
        # endregion

        # region main side tabs definition
        # 1 tab
        parameters_plate = soFrame(parameters_notebook, width=cC1_size[0])
        parameters_notebook.add(parameters_plate, image=self._createImage('plate.png'), )
        # 2 tab
        parameters_bolts = soFrame(parameters_notebook, width=cC1_size[0])
        parameters_notebook.add(parameters_bolts, image=self._createImage('bolt.png'), )
        # 3 tab
        distances_bolts = soFrame(parameters_notebook, width=cC1_size[0])
        parameters_notebook.add(distances_bolts, image=self._createImage('bolt.png'), )
        # 4 tab
        parameters_weld = soFrame(parameters_notebook, width=cC1_size[0])
        parameters_notebook.add(parameters_weld, image=self._createImage('weld.png'), )
        # endregion


        # region 1 tab plate
        plate_heading_frame = self.createTabElement_heading(parameters_plate,
                                                            trans(trans(u'Blachy')))
        plate_heading_frame.pack(fill=X, padx=3, pady=3)

        plate_dimensions_frame = soLabelFrame(parameters_plate,
                                              text=trans(u'Wymiary blachy [mm]'))
        plate_dimensions_frame.pack(fill=X, padx=3, pady=3)

        self.thickness_l1_frame = soFrame(plate_dimensions_frame)
        self.thickness_l1_frame.pack(fill=X)

        def validate_l1(l1):
            if l1 > self.var_dis_e.get():
                l1 = self.var_dis_e.get()
            return l1

        self.dis_l1_control = soControl(self.thickness_l1_frame,
                                        image=self._createImage('l1.gif'),
                                        variable=self.var_dis_l1,
                                        step=1.,
                                        round=1,
                                        max=500.,
                                        min=0.,
                                        showscale=False,
                                        selectmode='normal',
                                        width=6,
                                        allowempty=False,
                                        validatecmd=validate_l1)
        self.dis_l1_control.pack(fill=Y, side=LEFT)

        self.thickness_plate_control = soControl(self.thickness_l1_frame,
                                                 image=self._createImage('tp.gif'),
                                                 variable=self.var_thickness_plate,
                                                 step=1,
                                                 round=1,  # zaokraglenie - liczba miejsc po przecinku
                                                 min=12.,
                                                 max=26.,
                                                 showscale=False,
                                                 selectmode='normal',
                                                 width=6,
                                                 allowempty=False)
        self.thickness_plate_control.pack(fill=Y, side=RIGHT)

        self.dis_m_frame = soFrame(plate_dimensions_frame)
        self.dis_m_frame.pack(fill=X)

        self.dis_m1_control = soControl(self.dis_m_frame,
                                        image=self._createImage('m1.gif'),
                                        variable=self.var_dis_m1,
                                        step=1.,
                                        round=1,
                                        max=500.,
                                        min=0.,
                                        showscale=False,
                                        selectmode='normal',
                                        width=6,
                                        allowempty=False)
        self.dis_m1_control.pack(fill=Y, side=LEFT)

        self.dis_m2_control = soControl(self.dis_m_frame,
                                        image=self._createImage('m2.gif'),
                                        variable=self.var_dis_m2,
                                        step=1.,
                                        round=1,
                                        max=500.,
                                        min=0.,
                                        showscale=False,
                                        selectmode='normal',
                                        width=6,
                                        allowempty=False)
        self.dis_m2_control.pack(fill=Y, side=RIGHT)

        self.length_height_frame = soFrame(plate_dimensions_frame)
        self.length_height_frame.pack(fill=X)

        self.length_plate = dnComponentDlg.ResultValue(self.length_height_frame,
                                                       lImage=self._createImage('lp'),
                                                       format='%.1f')
        self.length_plate.pack(fill=Y, side=LEFT)

        self.height_plate = dnComponentDlg.ResultValue(self.length_height_frame,
                                                       lImage=self._createImage('hp'),
                                                       format='%.1f', )
        self.height_plate.pack(fill=Y, side=RIGHT)

        plate_steel_frame = soLabelFrame(parameters_plate,
                                         text=trans(u'Parametry stali'))
        plate_steel_frame.pack(fill=X, padx=3, pady=3)

        plate_steel_selection = soFrame(plate_steel_frame)
        plate_steel_selection.grid(row=0, sticky=N + W, padx=3, pady=3)
        plate_steel_selection_text = soLabel(plate_steel_selection,
                                             text=trans(u' Rodzaj stali:'))
        plate_steel_selection_text.grid(row=0, column=0, sticky=N + W, padx=0, pady=0)

        def on_steel_CB_change(value=None):
            value = value or self.var_selected_steel.get()
            plate_thickness = self.var_thickness_plate.get()
            if value == trans('Inna'):
                self.fy_plate_control['state'] = NORMAL
                self.fu_plate_control['state'] = NORMAL
            else:
                get_steel_str_error = get_steel_strength_EN(self.var_selected_steel.get(), plate_thickness)[2]
                self.fy_plate_control['state'] = DISABLED
                self.fu_plate_control['state'] = DISABLED
                if get_steel_str_error == 0:
                    self.var_fy_plate.set(get_steel_strength_EN(value, plate_thickness)[0])
                    self.var_fu_plate.set(get_steel_strength_EN(value, plate_thickness)[1])

        CB_values = get_steel_strength_EN_names()
        self.steel_selection_box = soComboBox(plate_steel_selection,
                                              state='readonly',
                                              width=15,
                                              values=CB_values,
                                              textvariable=self.var_selected_steel)
        self.steel_selection_box.grid(row=0, column=1, sticky=N + W, padx=0, pady=0)
        self.steel_selection_box.setOnSelectCommand(on_steel_CB_change)

        self.fy_plate_control = soControl(plate_steel_frame,
                                          image=self._createImage('f_yd'),
                                          variable=self.var_fy_plate,
                                          step=5.,
                                          round=0,
                                          max=1000.,
                                          min=20.,
                                          state=DISABLED,
                                          showscale=False,
                                          selectmode='normal',
                                          allowempty=False)
        self.fy_plate_control.grid(row=1, sticky=N + W, padx=3, pady=3)

        self.fu_plate_control = soControl(plate_steel_frame,
                                          image=self._createImage('f_ud'),
                                          variable=self.var_fu_plate,
                                          step=5.,
                                          round=0,
                                          max=1000.,
                                          min=20.,
                                          state=DISABLED,
                                          showscale=False,
                                          selectmode='normal',
                                          allowempty=False)
        self.fu_plate_control.grid(row=2, sticky=N + W, padx=3, pady=3)

        # endregion

        # region 2 tab bolts
        joint_heading_frame = self.createTabElement_heading(parameters_bolts,
                                                            trans(trans(u'Śruby')))
        joint_heading_frame.pack(fill=X, padx=3, pady=3)

        # self.joint_category_frame = soLabelFrame(parameters_bolts,
        #                                          text=trans(u'Kategoria połączenia'))
        # self.joint_category_frame.pack(fill=X, padx=3, pady=3)
        #
        # self.cat_D = soRadiobutton(self.joint_category_frame,
        #                            text=trans(u'kategoria D'),
        #                            value='D',
        #                            variable=self.var_joint_category)
        # self.cat_D.pack(side=LEFT, padx=3, pady=3)
        #
        # self.cat_E = soRadiobutton(self.joint_category_frame,
        #                            text=trans(u'kategoria E'),
        #                            value='E',
        #                            variable=self.var_joint_category)
        # self.cat_E.pack(side=RIGHT, padx=3, pady=3)



        self.joint_type_class_frame = soLabelFrame(parameters_bolts,
                                                   text=trans(u'Typ/Klasa:'))
        self.joint_type_class_frame.pack(fill=X, padx=3, pady=3)

        self.joint_type_CB = soComboBox(self.joint_type_class_frame,
                                        state='readonly',
                                        width=6,
                                        values=['M8', 'M10', 'M12', 'M16', 'M20', 'M22', 'M24', 'M27', 'M30', 'M36',
                                                'M42', 'M48'],
                                        textvariable=self.var_bolt_type)
        self.joint_type_CB.pack(side=LEFT, padx=3, pady=3)

        self.joint_class_CB = soComboBox(self.joint_type_class_frame,
                                         state='readonly',
                                         width=6,
                                         values=['4.6', '4.8', '5.6', '5.8', '6.8', '8.8', '10.9'],
                                         textvariable=self.var_bolt_class)
        self.joint_class_CB.pack(side=LEFT, padx=3, pady=3)

        self.joint_threaded_frame = soLabelFrame(parameters_bolts,
                                                 text=trans(u'Część ścinana'))
        self.joint_threaded_frame.pack(fill=X, padx=3, pady=3)

        self.threaded_check = soCheckbutton(self.joint_threaded_frame,
                                            text=trans(u'Gwintowana'),
                                            variable=self.var_is_threaded)  # Gwintowana =1  // niegwintowana =0
        self.threaded_check.pack(side=LEFT, padx=3, pady=3)

        self.column_hidden_frame = dnComponentDlg.HiddenFrame(parameters_bolts)
        self.column_hidden_frame.pack(fill=X, padx=3, pady=3)

        column_main_frame = soLabelFrame(self.column_hidden_frame, text=trans(u'Odl. od śrub do końca słupa'))
        self.column_hidden_frame.insert(column_main_frame, fill=X)

        column_above_frame = soFrame(column_main_frame)
        column_above_frame.pack(fill=X)

        self.above_column_hidden_control = soControl(column_above_frame,
                                                     label = u'Od górnego końca słupa: [cm] ',
                                                     variable=self.var_dis_s1,
                                                     step=1.,
                                                     round=1,
                                                     min=0.,
                                                     max=500.,
                                                     showscale=False,
                                                     selectmode='normal',
                                                     width=6,
                                                     allowempty=False)
        self.above_column_hidden_control.pack(fill=Y, side=RIGHT)

        column_under_frame = soFrame(column_main_frame)
        column_under_frame.pack(fill=X)


        self.under_column_hidden_control = soControl(column_under_frame,
                                                     label = u'Od dolnego końca słupa: [cm] ',
                                                     variable=self.var_dis_s2,
                                                     step=1.,
                                                     round=1,
                                                     min=0.,
                                                     max=500.,
                                                     showscale=False,
                                                     selectmode='normal',
                                                     width=6,
                                                     allowempty=False)
        self.under_column_hidden_control.pack(fill=Y, side=RIGHT)

        # endregion

        # region 3 tab bolts distances
        bolts_distances_heading = self.createTabElement_heading(distances_bolts,
                                                                trans(trans(u'Odległości śrub')))
        bolts_distances_heading.pack(fill=X, padx=3, pady=3)

        self.bolts_outside_frame = soLabelFrame(distances_bolts,
                                                text=trans(u'Śruby zewnętrzne'))
        self.bolts_outside_frame.pack(fill=X, padx=3, pady=3)

        self.bolts_above_frame = soFrame(self.bolts_outside_frame)
        self.bolts_above_frame.pack(fill=BOTH)

        self.bolts_above_check = soCheckbutton(self.bolts_above_frame,
                                               text=trans(u'Śruby nad belką'),
                                               variable=self.var_bolts_above, )
        self.bolts_above_check.pack(fill=Y, side=LEFT)

        self.above_hidden_control = soControl(self.bolts_above_frame,
                                              image=self._createImage('e1'),
                                              state=DISABLED,
                                              variable=self.var_dis_e1,
                                              step=1.,
                                              round=1,
                                              min=0.,
                                              max=100.,
                                              showscale=False,
                                              selectmode='normal',
                                              width=6,
                                              allowempty=False)
        self.above_hidden_control.pack(fill=Y, side=RIGHT)

        self.bolts_under_frame = soFrame(self.bolts_outside_frame)
        self.bolts_under_frame.pack(fill=BOTH)

        self.bolts_under_check = soCheckbutton(self.bolts_under_frame,
                                               text=trans(u'Śruby pod belką'),
                                               variable=self.var_bolts_under, )
        self.bolts_under_check.pack(fill=Y, side=LEFT)

        self.under_hidden_control = soControl(self.bolts_under_frame,
                                              image=self._createImage('e2'),
                                              state=DISABLED,
                                              variable=self.var_dis_e2,
                                              step=1.,
                                              round=1,
                                              min=0.,
                                              max=100.,
                                              showscale=False,
                                              selectmode='normal',
                                              width=6,
                                              allowempty=False)
        self.under_hidden_control.pack(fill=Y, side=RIGHT)

        self.dis_e_frame = soFrame(self.bolts_outside_frame)
        self.dis_e_frame.pack(fill=X)

        def validate_e(e):
            if e < self.var_dis_l1.get():
                e = self.var_dis_l1.get()
            return e

        self.dis_e_control = soControl(self.dis_e_frame,
                                       image=self._createImage('e.gif'),
                                       variable=self.var_dis_e,
                                       step=1.,
                                       round=1,
                                       max=500.,
                                       min=0.,
                                       showscale=False,
                                       selectmode='normal',
                                       width=6,
                                       allowempty=False,
                                       validatecmd=validate_e)
        self.dis_e_control.pack(fill=Y, side=LEFT)

        self.bolts_inside_frame = soLabelFrame(distances_bolts,
                                               text=trans(u'Śruby wewnętrzne - góra'))
        self.bolts_inside_frame.pack(fill=X, padx=3, pady=3)

        self.number_p1_frame = soFrame(self.bolts_inside_frame)
        self.number_p1_frame.pack(fill=X)

        self.bolts_number_control = soControl(self.number_p1_frame,
                                              label=trans(u'Rzędy = '),
                                              variable=self.var_rows_up,
                                              step=1,
                                              round=0,
                                              max=5,
                                              min=0,
                                              showscale=False,
                                              selectmode='normal',
                                              width=6,
                                              allowempty=False, )
        self.bolts_number_control.pack(fill=Y, side=LEFT)

        # def validate_p1():
        # sprawdzic czy sie sruby zmieszcza :P
        self.dis_p1_control = soControl(self.number_p1_frame,
                                        image=self._createImage('p1.gif'),
                                        variable=self.var_dis_p1,
                                        state=NORMAL,
                                        step=1.,
                                        round=1,
                                        max=500.,
                                        min=0.,
                                        showscale=False,
                                        selectmode='normal',
                                        width=6,
                                        allowempty=False)
        self.dis_p1_control.pack(fill=Y, side=RIGHT)

        # def validate_p2():
        # sprawdzic czy sie sruby zmieszcza :P
        self.dis_p2_control = soControl(self.bolts_inside_frame,
                                        image=self._createImage('p2.gif'),
                                        variable=self.var_dis_p2,
                                        state=NORMAL,
                                        step=1.,
                                        round=1,
                                        max=500.,
                                        min=0.,
                                        showscale=False,
                                        selectmode='normal',
                                        width=6,
                                        allowempty=False)
        self.dis_p2_control.pack(side=RIGHT)

        self.bolts_inside_down_frame = soLabelFrame(distances_bolts,
                                                    text=trans(u'Śruby wewnętrzne - dół'))
        self.bolts_inside_down_frame.pack(fill=X, padx=3, pady=3)

        self.number_p3_frame = soFrame(self.bolts_inside_down_frame)
        self.number_p3_frame.pack(fill=X)

        self.bolts_number_down_control = soControl(self.number_p3_frame,
                                                   label=trans(u'Rzędy = '),
                                                   variable=self.var_rows_down,
                                                   step=1,
                                                   round=0,
                                                   max=5,
                                                   min=0,
                                                   showscale=False,
                                                   selectmode='normal',
                                                   width=6,
                                                   allowempty=False, )
        self.bolts_number_down_control.pack(fill=Y, side=LEFT)

        self.dis_p3_control = soControl(self.number_p3_frame,
                                        image=self._createImage('p3.gif'),
                                        variable=self.var_dis_p3,
                                        state=NORMAL,
                                        step=1.,
                                        round=1,
                                        max=500.,
                                        min=0.,
                                        showscale=False,
                                        selectmode='normal',
                                        width=6,
                                        allowempty=False)
        self.dis_p3_control.pack(fill=Y, side=RIGHT)

        self.dis_p4_control = soControl(self.bolts_inside_down_frame,
                                        image=self._createImage('p4.gif'),
                                        variable=self.var_dis_p4,
                                        state=NORMAL,
                                        step=1.,
                                        round=1,
                                        max=500.,
                                        min=0.,
                                        showscale=False,
                                        selectmode='normal',
                                        width=6,
                                        allowempty=False)
        self.dis_p4_control.pack(side=RIGHT)

        # endregion

        # region 4 tab welds
        weld_heading = self.createTabElement_heading(parameters_weld,
                                                     trans(trans(u'Spoiny')))
        weld_heading.pack(pady=3, fill=X, padx=3)

        self.weld_type_frame = soLabelFrame(parameters_weld,
                                            text=trans(u'Typ spoiny:'))
        self.weld_type_frame.pack(fill=X, padx=3, pady=3)

        self.weld_type_CB = soComboBox(self.weld_type_frame,
                                       state='readonly',
                                       width=12,
                                       values=[trans(u'Pachwinowa'),
                                               trans(u'Czołowa')],
                                       textvariable=self.var_weld_type)
        self.weld_type_CB.pack(fill=Y, side=LEFT, padx=3, pady=3)

        self.switch_frame = dnComponentDlg.SwitchFrame(parameters_weld,
                                                       padding=0)
        self.switch_frame.pack(fill=X, padx=3, pady=3)

        set_aw_frame = soLabelFrame(self.switch_frame,
                                    text=trans(u'Parametry spoin'))
        set_aw_frame.pack(side=LEFT, fill=Y)

        self.set_aw_control = soControl(set_aw_frame,
                                        image=self._createImage('aw'),
                                        variable=self.var_aw,
                                        step=1.,
                                        round=0,
                                        selectmode='normal',
                                        width=6,
                                        min=3.,
                                        max=16.,
                                        showscale=False,
                                        allowempty=False, )
        self.set_aw_control.pack(side=LEFT, fill=Y)

        self.weld_info = soLabel(self.switch_frame,
                                 text=trans(u'Spoina czołowa z pełnym przetopem.'))
        self.weld_info.pack(fill=BOTH)

        self.switch_frame.add(set_aw_frame)
        self.switch_frame.add(self.weld_info)
        # endregion

        self.addUpdatePermanentPanelFunctions([
            # add update functions for permanent panel here
        ])

    # create main tab
    def createTab_results(self, tab):
        # use this to keep padding consistent
        tab_opts2 = {"padx": 3, "pady": 0, "sticky": NSEW}

        # region main result frame
        # tab.grid_columnconfigure(0, weight=1)
        self.switch_main_frame = dnComponentDlg.SwitchFrame(tab)
        self.switch_main_frame.pack(fill=BOTH)

        self.error_frame = soFrame(self.switch_main_frame)
        self.error_frame.pack(fill=BOTH)

        error_label = soLabel(self.error_frame, text=trans(u'Brak obliczeń ze względu na błędy projektowe.'),
                              foreground='red', font=('', 15))
        error_label.pack(expand=True)

        self.results_frame = soFrame(self.switch_main_frame)
        self.results_frame.pack(fill=BOTH)
        self.switch_main_frame.add(self.error_frame)
        self.switch_main_frame.add(self.results_frame)
        # endregion

        # region sily NTM
        # extremal_load_comb_labelframe = soLabelFrame(self.result_frame,
        #                                              text=trans(u'Najbardziej niekorzystna kombinacja obciążeń'))
        # extremal_load_comb_labelframe.pack(fill=X)
        # # wewnetrzna ramka ekstremalnych sił przekrojowych
        # extremal_load_comb_frame = soFrame(extremal_load_comb_labelframe)
        # extremal_load_comb_frame.pack(fill=X)
        #
        # # sterowanie przesunieciem ramek
        # padxF = 0  # Frame z ResultFrame
        # padxCB = 0  # CheckButton
        #
        # # SIŁA NORMALNA
        # # switchFrame
        # self.N_switchframe = dnComponentDlg.SwitchFrame(extremal_load_comb_frame, padding=0)
        # self.N_switchframe.pack(side=LEFT)
        # # wyświetlanie
        # self.extremal_load_comb_N_frame = soFrame(self.N_switchframe)
        # self.extremal_load_comb_N = dnComponentDlg.ResultValue(self.extremal_load_comb_N_frame,
        #                                                        lImage=self._createImage('load_N'),
        #                                                        rImage=self._createImage('unit_kN'), format='%3.2f')
        # self.extremal_load_comb_N.pack(side=LEFT)
        # # zmiana wartości
        # self.enter_N_frame = soFrame(self.N_switchframe)
        #
        # def min_max_N_validate(x):
        #     try:
        #         x = float(x)
        #     except:
        #         return self.var_load_N.get()
        #     if x < -999.:
        #         x = -999.
        #     if x > 999.:
        #         x = 999.
        #     return x
        #
        # self.enter_N_control = soControl(self.enter_N_frame,
        #                                  image=self._createImage('load_N'),
        #                                  variable=self.var_load_N,
        #                                  step=1.,
        #                                  allowempty=False,
        #                                  validatecmd=min_max_N_validate)
        # self.enter_N_control['selectmode'] = 'normal'
        # self.enter_N_control.entry['width'] = 5
        # self.enter_N_control.pack(side=LEFT)
        # # wprowadzenie ramek do swithFrame
        # self.N_switchframe.add(self.extremal_load_comb_N_frame)
        # self.N_switchframe.add(self.enter_N_frame)
        #
        # # SIŁA TNĄCA
        # # switchFrame
        # self.V_switchframe = dnComponentDlg.SwitchFrame(extremal_load_comb_frame, padding=0)
        # self.V_switchframe.pack(side=LEFT)
        # # wyświetlanie
        # self.extremal_load_comb_V_frame = soFrame(self.V_switchframe)
        # self.extremal_load_comb_V = dnComponentDlg.ResultValue(self.extremal_load_comb_V_frame,
        #                                                        lImage=self._createImage('load_V'),
        #                                                        rImage=self._createImage('unit_kN'), format='%3.2f')
        # self.extremal_load_comb_V.pack(side=LEFT)
        # # zmiana wartości
        # self.enter_V_frame = soFrame(self.V_switchframe)
        #
        # def min_max_V_validate(x):
        #     try:
        #         x = float(x)
        #     except:
        #         return self.var_load_V.get()
        #     if x < -999.:
        #         x = -999.
        #     if x > 999.:
        #         x = 999.
        #     return x
        #
        # self.enter_V_control = soControl(self.enter_V_frame,
        #                                  image=self._createImage('load_V'),
        #                                  variable=self.var_load_V,
        #                                  step=1.,
        #                                  allowempty=False,
        #                                  validatecmd=min_max_V_validate)
        # self.enter_V_control['selectmode'] = 'normal'
        # self.enter_V_control.entry['width'] = 5
        # self.enter_V_control.pack(side=LEFT)
        # # wprowadzenie ramek do swithFrame
        # self.V_switchframe.add(self.extremal_load_comb_V_frame)
        # self.V_switchframe.add(self.enter_V_frame)
        #
        # # MOMENT
        # # switchFrame
        # self.M_switchframe = dnComponentDlg.SwitchFrame(extremal_load_comb_frame, padding=0)
        # self.M_switchframe.pack(side=LEFT)
        # # wyświetlanie
        # self.extremal_load_comb_M_frame = soFrame(self.M_switchframe)
        # self.extremal_load_comb_M = dnComponentDlg.ResultValue(self.extremal_load_comb_M_frame,
        #                                                        lImage=self._createImage('load_M'),
        #                                                        rImage=self._createImage('unit_kNm'), format='%3.2f')
        # self.extremal_load_comb_M.pack(side=LEFT)
        # # zmiana wartości
        # self.enter_M_frame = soFrame(self.M_switchframe)
        #
        # def min_max_M_validate(x):
        #     try:
        #         x = float(x)
        #     except:
        #         return self.var_load_M.get()
        #     if x < -999.:
        #         x = -999.
        #     if x > 999.:
        #         x = 999.
        #     return x
        #
        # self.enter_M_control = soControl(self.enter_M_frame,
        #                                  image=self._createImage('load_M'),
        #                                  variable=self.var_load_M,
        #                                  step=1.,
        #                                  allowempty=False,
        #                                  validatecmd=min_max_M_validate)
        # self.enter_M_control['selectmode'] = 'normal'
        # self.enter_M_control.entry['width'] = 5
        # self.enter_M_control.pack(side=LEFT)
        # # wprowadzenie ramek do swithFrame
        # self.M_switchframe.add(self.extremal_load_comb_M_frame)
        # self.M_switchframe.add(self.enter_M_frame)
        #
        # def on_check_load_change():
        #     if self.var_load_change.get():
        #         self.M_switchframe.switch(1)
        #         self.V_switchframe.switch(1)
        #         self.N_switchframe.switch(1)
        #     else:
        #         self.M_switchframe.switch(0)
        #         self.V_switchframe.switch(0)
        #         self.N_switchframe.switch(0)
        #
        # self.change_extremal_load_comb_checkbutton = soCheckbutton(extremal_load_comb_frame,
        #                                                            image=self._createImage('pencil.png'),
        #                                                            variable=self.var_load_change,
        #                                                            command=on_check_load_change)
        # self.change_extremal_load_comb_checkbutton.pack(side=LEFT)
        #
        # def getLoadGroups():
        #     rObj = self.getCompObj().getResults().getResult('summary_results')
        #     if rObj['extremal_load_group_USL']:
        #         return rObj['extremal_load_group_USL']
        #     else:
        #         return None
        #
        # extremal_combLoadGroups = self.insertCombLoadGroupsInfo(extremal_load_comb_frame,
        #                                                         getLoadGroupsFun=getLoadGroups)
        # extremal_combLoadGroups.pack(side=LEFT)
        # endregion

        # region shear
        shear_frame = soLabelFrame(self.results_frame, text=trans(u'Wytrzymałość na ścinanie'))
        shear_frame.pack(fill=X)

        self.shear_comparison = dnComponentDlg.Comparison(shear_frame,
                                                          lImage=self._createImage('load_V'),
                                                          rImage=self._createImage('V_Rd'),
                                                          lFormat='%.2f', rFormat='%.2f')
        self.shear_comparison.pack(fill=Y)
        # endregion

        # region bending
        bending_frame = soLabelFrame(self.results_frame, text=trans(u'Wytrzymałość na zginanie'))
        bending_frame.pack(fill=X)

        self.bending_comparison = dnComponentDlg.Comparison(bending_frame,
                                                            lImage=self._createImage('load_M'),
                                                            rImage=self._createImage('M_Rd'),
                                                            lFormat='%.2f', rFormat='%.2f')
        self.bending_comparison.pack(fill=Y)
        # endregion

        # region tension
        tension_frame = soLabelFrame(self.results_frame, text=trans(u'Wytrzymałość na rozciąganie'))
        tension_frame.pack(fill=X)

        self.tension_comparison = dnComponentDlg.Comparison(tension_frame,
                                                            lImage=self._createImage('load_N'),
                                                            rImage=self._createImage('N_Rd'),
                                                            lFormat='%.2f', rFormat='%.2f')
        self.tension_comparison.pack(fill=Y)
        # endregion

        # region bendinging_tension
        bending_tension_frame = soLabelFrame(self.results_frame, text=trans(u'Wytrzymałość na zginanie z rozciąganiem'))
        bending_tension_frame.pack(fill=X)

        self.bending_tension_comparison = dnComponentDlg.Comparison(bending_tension_frame,
                                                                    lImage=self._createImage('MEd_NEd'),
                                                                    lFormat='%.2f', rFormat='%.0f')
        self.bending_tension_comparison.pack(fill=Y)
        # endregion

        # region column hidden frame
        self.column_result_hidden_frame = dnComponentDlg.HiddenFrame(self.results_frame)
        self.column_result_hidden_frame.pack(fill=X)

        column_frame = soLabelFrame(self.column_result_hidden_frame, text=trans(u'Wytrzymałość na ściecie środnika'))
        self.column_result_hidden_frame.insert(column_frame, fill=X)

        self.column_shear_comparison = dnComponentDlg.Comparison(column_frame,
                                                        lImage=self._createImage('V_wp_Ed'),
                                                        rImage=self._createImage('V_wp_Rd'),
                                                        lFormat='%.1f', rFormat='%.1f')
        self.column_shear_comparison.pack(fill=X)
        # endregion

        # region welds hidden frame
        self.weld_hidden_frame = dnComponentDlg.HiddenFrame(self.results_frame)
        self.weld_hidden_frame.pack(fill=X)

        weld_frame = soLabelFrame(self.weld_hidden_frame, text=trans(u'Wytrzymałość spoiny'))
        self.weld_hidden_frame.insert(weld_frame, fill=X)

        self.Aw_result = dnComponentDlg.ResultValue(weld_frame, lImage=self._createImage('Aw'),
                                                    rImage=self._createImage('unit_mm2'), format='%.2f')
        self.Aw_result.grid(row=0, column=0, **tab_opts2)

        self.sigma_p_result = dnComponentDlg.ResultValue(weld_frame,
                                                         lImage=self._createImage('sigma_perpendicular'),
                                                         rImage=self._createImage('unit_MPa'), format='%.2f')
        self.sigma_p_result.grid(row=0, column=1, **tab_opts2)

        self.tau_p_result = dnComponentDlg.ResultValue(weld_frame,
                                                       lImage=self._createImage('tau_perpendicular'),
                                                       rImage=self._createImage('unit_MPa'), format='%.2f')
        self.tau_p_result.grid(row=0, column=2, **tab_opts2)

        self.tauII_result = dnComponentDlg.ResultValue(weld_frame,
                                                       lImage=self._createImage('tau_parallel'),
                                                       rImage=self._createImage('unit_MPa'), format='%.2f')
        self.tauII_result.grid(row=0, column=3, **tab_opts2)

        self.weld_comparison = dnComponentDlg.Comparison(weld_frame,
                                                         lImage=self._createImage('sig_wyp'),
                                                         rImage=self._createImage('fu'),
                                                         lFormat='%.1f', rFormat='%.1f')
        self.weld_comparison.grid(row=1, column=0, columnspan=2, sticky=W + E + S, pady=0)

        self.weld2_comparison = dnComponentDlg.Comparison(weld_frame,
                                                          lImage=self._createImage('sig'),
                                                          rImage=self._createImage('sig_lim'),
                                                          lFormat='%.1f', rFormat='%.1f')
        self.weld2_comparison.grid(row=1, column=2, columnspan=2, sticky=W + E + S, pady=0)
        # endregion

    def updatePermanentPanel(self):
        # update permanent panel
        self.updateCanvas()

        if self.getCompObj().connection_type == CONNECTION_BEAM_TO_COLUMN:
            self.column_hidden_frame.show()
        else:
            self.column_hidden_frame.hide()

        if self.var_weld_type.get() == trans(u'Pachwinowa'):
            self.switch_frame.switch(0)
        else:
            self.switch_frame.switch(1)

        if self.var_bolts_under.get():
            self.under_hidden_control['state'] = NORMAL
        else:
            self.under_hidden_control['state'] = DISABLED

        if self.var_bolts_above.get():
            self.above_hidden_control['state'] = NORMAL
        else:
            self.above_hidden_control['state'] = DISABLED

        if self.var_rows_up.get() == 0.:
            self.dis_p1_control['state'] = DISABLED
            self.dis_p2_control['state'] = DISABLED
        elif self.var_rows_up.get() == 1.:
            self.dis_p1_control['state'] = NORMAL
            self.dis_p2_control['state'] = DISABLED
        else:
            self.dis_p1_control['state'] = NORMAL
            self.dis_p2_control['state'] = NORMAL

        if self.var_rows_down.get() == 0.:
            self.dis_p3_control['state'] = DISABLED
            self.dis_p4_control['state'] = DISABLED
        elif self.var_rows_down.get() == 1.:
            self.dis_p3_control['state'] = NORMAL
            self.dis_p4_control['state'] = DISABLED
        else:
            self.dis_p3_control['state'] = NORMAL
            self.dis_p4_control['state'] = NORMAL

        if self.getCompObj().getResults().hasResult('plate'):
            plate = self.getCompObj().getResults().getResult('plate')
            self.length_plate.setValue(plate['lp'])
            self.height_plate.setValue(plate['hp'])

    def updateCanvas(self):
        # in this function, you basically draw anything on your canvases

        # erase everything
        self.cC1.delete(ALL)
        self.cC1.set_default()
        self.cC2.delete(ALL)
        self.cC2.set_default()
        # data
        if self.getCompObj().getResults().isCalculated():
            prof = self.getCompObj().getResults().getResult('prof')
            prof_c = self.getCompObj().getResults().getResult('prof_c')
            plate = self.getCompObj().getResults().getResult('plate')
            draw = self.getCompObj().getResults().getResult('draw_results')
            distances = self.getCompObj().getResults().getResult('distances')
            bolt_type = self.var_bolt_type.get()
            S = bolt_size[bolt_type][1]
            # plate
            dnRigidBeamLib.draw_plate(self.cC1, distances, prof['bfu'], prof['h'])
            dnRigidBeamLib.draw_side_plate(self.cC2, distances, prof['h'], -plate['tp'])
            if self.getCompObj().connection_type == CONNECTION_BEAM_TO_BEAM:
                dnRigidBeamLib.draw_side_plate(self.cC2, distances, prof['h'], plate['tp'])
            # profile
            dnRigidBeamLib.draw_profile(self.cC1, draw['profile_coords'])
            dnRigidBeamLib.draw_side_profile(self.cC2, -plate['tp'], draw['side_coords1'], -draw['profile_length1'])
            if self.getCompObj().connection_type == CONNECTION_BEAM_TO_BEAM:
                dnRigidBeamLib.draw_side_profile(self.cC2, plate['tp'], draw['side_coords2'], draw['profile_length2'])
            else:
                dnRigidBeamLib.draw_side_column(self.cC2, draw['side_coords2'], draw['profile_length2'], prof_c['h'])

            # welds
            if self.var_weld_type.get() == trans(u'Pachwinowa'):
                dnRigidBeamLib.draw_welds(self.cC1, prof, self.var_aw.get())
                dnRigidBeamLib.draw_side_welds(self.cC2, prof['h'], prof['tf'], prof['r'], plate['tp'],
                                               self.var_aw.get(), self.getCompObj().connection_type == CONNECTION_BEAM_TO_COLUMN)

            # bolts
            dnRigidBeamLib.bolt_grid_setup(self.cC1, self.var_rows_up.get(), self.var_rows_down.get(),
                                           distances, prof, S, self.var_bolts_above.get(), self.var_bolts_under.get())
            dnRigidBeamLib.bolt_side_grid_setup(self.cC2, self.var_rows_up.get(), self.var_rows_down.get(),
                                                distances, S, bolt_type, plate['tp'], prof['h'], prof['tf'],
                                                self.var_bolts_above.get(), self.var_bolts_under.get(),
                                                self.getCompObj().connection_type == CONNECTION_BEAM_TO_COLUMN, prof_c['tf'])
            # dimensions
            dnRigidBeamLib.draw_horizontal_dimension(self.cC1, plate, distances, prof['h'])
            dnRigidBeamLib.draw_vertical_dimension(self.cC1, plate['lp'], distances, prof['tf'], prof['h'])
            dnRigidBeamLib.draw_vertical_dimension(self.cC2, 6 * plate['tp'], distances, prof['tf'], prof['h'])
            dnRigidBeamLib.draw_horizontal_side_dimension(self.cC2, prof['h'], distances['m2'], distances['e2'],
                                                          plate['tp'])

            # spacer
            dnRigidBeamLib.draw_boundary(self.cC1, 1.2 * plate['lp'], 1.2 * plate['hp'])
            dnRigidBeamLib.draw_boundary(self.cC2, 1.2 * plate['lp'], 1.2 * plate['hp'])
            # this fits drawings to your canvases
            self.cC1.fit_to_view()
            self.cC2.fit_to_view()

    def updateTab_results(self):
        self.weld_hidden_frame.show(self.var_weld_type.get() == trans(u'Pachwinowa'))

        self.column_result_hidden_frame.show(self.getCompObj().connection_type == CONNECTION_BEAM_TO_COLUMN)

        self.switch_main_frame.switch(self.getCompObj().getResults().isCalculated())

        r_obj = self.getCompObj().getResults()
        shear_comb_data = None
        bending_comb_data = None
        tension_comb_data = None
        bending_tension_comb_data = None
        column_shear_comb_data = None
        weld_comb_data = None
        weld2_comb_data = None
        if r_obj.isCalculated():
            shear_res = r_obj.getResult(EXTREMAL_SHEAR_RATIO)
            bending_res = r_obj.getResult(EXTREMAL_BENDING_RATIO)
            tension_res = r_obj.getResult(EXTREMAL_TENSION_RATIO)
            bending_tension_res = r_obj.getResult(EXTREMAL_BENDING_TENSION_RATIO)
            column_shear_res = r_obj.getResult(EXTREMAL_COLUMN_SHEAR_RATIO)
            weld_res = r_obj.getResult(EXTREMAL_WELD_RATIO)
            weld2_res = r_obj.getResult(EXTREMAL_WELD2_RATIO)
            if shear_res:
                shear_comb_data = self.find_the_worst(shear_res)
            if bending_res:
                bending_comb_data = self.find_the_worst(bending_res)
            if tension_res:
                tension_comb_data = self.find_the_worst(tension_res)
            if bending_tension_res:
                bending_tension_comb_data = self.find_the_worst(bending_tension_res)
            if column_shear_res:
                column_shear_comb_data = self.find_the_worst(column_shear_res)
            if weld_res and weld2_res:
                weld_comb_data = self.find_the_worst(weld_res)
                weld2_comb_data = self.find_the_worst(weld2_res)

        if shear_comb_data is not None:
            self.shear_comparison.setValues(shear_comb_data[0]['loading'], shear_comb_data[0]['resistance'])
        if bending_comb_data is not None:
            self.bending_comparison.setValues(bending_comb_data[0]['loading'], bending_comb_data[0]['resistance'])
        if tension_comb_data is not None:
            self.tension_comparison.setValues(tension_comb_data[0]['loading'], tension_comb_data[0]['resistance'])
        if bending_tension_comb_data is not None:
            self.bending_tension_comparison.setValues(bending_tension_comb_data[0]['ratio'], 1)
        if column_shear_comb_data is not None:
            self.column_shear_comparison.setValues(column_shear_comb_data[0]['loading'],
                                                   column_shear_comb_data[0]['resistance'])

        if weld_comb_data and weld2_comb_data is not None:
            self.Aw_result.setValue(weld_comb_data[0]['Aw'])
            self.sigma_p_result.setValue(weld_comb_data[0]['sig_pros'])
            self.tau_p_result.setValue(weld_comb_data[0]['sig_pros'])
            self.tauII_result.setValue(weld_comb_data[0]['tauII'])
            self.weld_comparison.setValues(weld_comb_data[0]['loading'], weld_comb_data[0]['resistance'])
            self.weld2_comparison.setValues(weld2_comb_data[0]['loading'], weld2_comb_data[0]['resistance'])

    def updateTabsStatus(self):
        # sometimes you to fill this function
        pass

    def getSize(self):
        # size of CompDlg in px
        return 765, 550

CONNECTION_BEAM_TO_BEAM = 0
CONNECTION_BEAM_TO_COLUMN = 1

# this is your main component, here you perform all of your calculations
class RigidBeamConnection(dnComponent.NodeComponent):
    ### FILL THIS CAREFULY ###
    type = dnConstants.COMP_USER_APP
    connection_type = CONNECTION_BEAM_TO_BEAM
    name = trans(u'Połączenie doczołowe dwóch belek')
    description = trans(u'Wymiarowanie połączenia doczołowego dwóch belek wg PN-EN 1993-1-8')
    dirPath = os.path.join(dnConstants.LIB_DIR_PATH, 'components/node/steelConnections_EC/RigidBeamToBeamOrColumn/')
    iconPath = os.path.join(dnConstants.LIB_DIR_PATH,
                            'components/node/steelConnections_EC/RigidBeamToBeamOrColumn/img/icon_beam.gif')
    languages = [soConstants.ENGLISH]
    standardType = soConstants.EUROCODE_STANDARD
    summarySubjects = [
        EXTREMAL_SHEAR_RATIO,
        EXTREMAL_BENDING_RATIO,
        EXTREMAL_TENSION_RATIO,
        EXTREMAL_BENDING_TENSION_RATIO,
        EXTREMAL_COLUMN_SHEAR_RATIO,
        EXTREMAL_WELD_RATIO,
        EXTREMAL_WELD2_RATIO,
    ]

    ###

    # you dont need to specify anything here
    def __init__(self, parent, itemId):

        dnComponent.NodeComponent.__init__(self, parent, itemId)

    # here you set default values for all of your variables
    def setDefault(self):

        dnComponent.NodeComponent.setDefault(self)



        # here you init params for dlg parameters that are registered in setVars function of dlg component
        # self. means that they will be accessible thought the PipeSpliceConnection class and is neccessary to use
        self.thickness_plate = 12.
        self.fy_plate = 235.
        self.fu_plate = 360.
        self.selected_steel = 'S 235'
        self.joint_category = 'D'
        self.bolt_type = 'M10'
        self.bolt_class = '8.8'
        self.is_threaded = 0.
        self.bolts_above = 0.
        self.weld_type = trans(u'Pachwinowa')
        self.aw = 4.  # mm
        self.bolts_above = 0
        self.bolts_under = 0
        self.dis_e1 = 0.
        self.dis_e2 = 0.
        self.dis_m1 = 20.
        self.dis_m2 = 20.
        self.dis_e = 50.
        self.dis_l1 = 30.
        self.dis_p1 = 20.
        self.dis_p2 = 30.
        self.rows_up = 2
        self.rows_down = 1
        self.dis_p3 = 20.
        self.dis_p4 = 30.
        self.dis_s1 = 500.
        self.dis_s2 = 500.

        self.which_column = 1
        self.column_on_right = 1
        if self.connection_type == CONNECTION_BEAM_TO_COLUMN:
            self.which_column = dnRigidBeamLib.check_which_is_column(self.getItem())
            self.column_on_right = dnRigidBeamLib.check_if_column_on_right_side(self.getItem(), self.which_column)
        self.prof = dnRigidBeamLib.get_profile_parameters(self.getItem(), 1-self.which_column)
        self.prof_c = dnRigidBeamLib.get_profile_parameters(self.getItem(), self.which_column)

    def doCustomCheck(self):

        def error(text):
            self.getMessageManager().addMessage(trans(text),
                                                type=dnComponent.MSG_TYPE_ERROR)

        if not dnRigidBeamLib.check_elements_number(self.getItem()):
            error(u'Niedopuszczalna ilość dochodzących elementów.')
            return False

        if not self.connection_type == CONNECTION_BEAM_TO_COLUMN:
            if not dnRigidBeamLib.check_beams_angle(self.getItem(), self.connection_type, self.which_column):
                error(u'Obie belki muszą być poziome')
                return False
        else:
            if not dnRigidBeamLib.check_beams_angle(self.getItem(), self.connection_type, self.which_column):
                error(u'Belka musi byc pozioma, a słup pionowy')
                return False


        if not dnRigidBeamLib.check_profile(self.getItem()):
            error(u'Nieprawidłowy profil.')
            return False
        if not self.connection_type == CONNECTION_BEAM_TO_COLUMN:
            if not dnRigidBeamLib.check_profiles_same(self.getItem()):
                error(u'Profile belek muszą być takie same.')
                # return False


        if self.weld_type == trans(u'Pachwinowa'):
            aw = self.aw
            if not dnRigidBeamLib.check_is_weld_out_plate(self.bolts_above, self.bolts_under, aw, self.dis_m1,
                                                          self.dis_m2,
                                                          self.dis_e1, self.dis_e2):
                error(u'Spoina jest poza blachą.')
                # return False
            if not dnRigidBeamLib.check_weld_length(dnRigidBeamLib.calc_weld_lengths(self.prof, 0), aw):
                error(u'Pojedyńcze spoiny są zbyt krótkie(<30mm lub 6a).')
                # return False
        else:
            aw = 0.

        if not dnRigidBeamLib.check_is_min2_rows(self.bolts_above, self.bolts_under, self.rows_up, self.rows_down):
            error(trans(u'Za mało rzędów śrub.'))
            return False

        if not dnRigidBeamLib.check_tw_e(self.dis_e, self.dis_l1, self.bolt_type, aw, self.prof['bfu'],
                                         self.prof['tw']):
            error(u'Śruby są za blisko środnika.')
            # return False

        if not dnRigidBeamLib.check_max_e(self.dis_e, self.thickness_plate):
            error(u'Za duża wartość e.')
            # return False

        if not dnRigidBeamLib.check_min_e(self.dis_e, self.bolt_type):
            error(u'Za mała odległość śrub od krawędzi blachy(e).')
            # return False


        if self.bolts_above:
            if not dnRigidBeamLib.check_weld_bolt_distance(self.dis_m1, aw, self.bolt_type):
                error(u'Za mała odległość śruby od spoiny(m1).')
                # return False
            if not dnRigidBeamLib.check_min_e1e2(self.dis_e1, self.bolt_type):
                error(u'Za mała odległość śrub od krawędzi blachy(e1).')
                # return False
            if not dnRigidBeamLib.check_max_e1e2(self.dis_e1, self.thickness_plate):
                error(u'Za duża wartość e1.')
                # return False

        if self.bolts_under:
            if not dnRigidBeamLib.check_weld_bolt_distance(self.dis_m2, aw, self.bolt_type):
                error(u'Za mała odległość śruby od spoiny(m2).')
                # return False
            if not dnRigidBeamLib.check_min_e1e2(self.dis_e2, self.bolt_type):
                error(u'Za mała odległość śrub od krawędzi blachy(e2).')
                # return False
            if not dnRigidBeamLib.check_max_e1e2(self.dis_e2, self.thickness_plate):
                error(u'Za duża wartość e2.')
                # return False

        if self.rows_up >= 1:
            if not dnRigidBeamLib.check_min_p1p3(self.dis_p1, aw, self.bolt_type):
                error(u'Śruby za blisko pasa górnego(p1).')
                # return False
        if self.rows_up >= 2:
            if not dnRigidBeamLib.check_min_p2p4(self.dis_p2, self.bolt_type):
                error(u'Za mała odległość między górnymi rzędami śrub(p2).')
                # return False
            if not dnRigidBeamLib.check_max_p2p4(self.dis_p2, self.thickness_plate):
                error(u'Za duża odległość między górnymi rzędami śrub(p2)')
                # return False

        if self.rows_down >= 1:
            if not dnRigidBeamLib.check_min_p1p3(self.dis_p3, aw, self.bolt_type):
                error(u'Śruby za blisko pasa dolnego(p3).')
                # return False
        if self.rows_down >= 2:
            if not dnRigidBeamLib.check_min_p2p4(self.dis_p4, self.bolt_type):
                error(u'Za mała odległość między dolnymi rzędami śrub(p4).')
                # return False
            if not dnRigidBeamLib.check_max_p2p4(self.dis_p4, self.thickness_plate):
                error(u'Za duża odległość między dolnymi rzędami śrub(p4)')
                # return False

        if self.rows_down >= 1 and self.rows_up >= 1:
            if not dnRigidBeamLib.check_dist_between_up_down_rows(self.dis_p1, self.dis_p2, self.dis_p3,
                                                                  self.dis_p4, self.prof['h'], self.prof['tf'],
                                                                  self.rows_up,
                                                                  self.rows_down, self.bolt_type):
                error(u'Za mała odległość między rzędami górnymi i dolnymi')
                # return False

        return True

    def doBeforeCalculate(self):
        return True

    def doCalculate(self, soft=False):

        # getting distances
        if not self.bolts_above:
            e1 = 0
        else:
            e1 = self.dis_e1
        if not self.bolts_under:
            e2 = 0
        else:
            e2 = self.dis_e2

        if self.rows_up == 1:
            p2 = 0
            p1 = self.dis_p1
        elif self.rows_up < 0.5:
            p1 = 0
            p2 = 0
        else:
            p1 = self.dis_p1
            p2 = self.dis_p2

        if self.rows_down == 1:
            p4 = 0
            p3 = self.dis_p3
        elif self.rows_down < 0.5:
            p3 = 0
            p4 = 0
        else:
            p3 = self.dis_p3
            p4 = self.dis_p4

        distances = {
            'e1': e1,
            'e2': e2,
            'e': self.dis_e,
            'm1': self.dis_m1,
            'm2': self.dis_m2,
            'l1': self.dis_l1,
            'p1': p1,
            'p2': p2,
            'p3': p3,
            'p4': p4,
        }
        self.getResults().setResults({'distances': distances})

        height_plate = self.prof['h'] + self.dis_m1 + self.dis_m2 + e1 + e2
        length_plate = self.prof['bfu'] + self.dis_l1 * 2
        plate = {
            'hp': height_plate,
            'lp': length_plate,
            'tp': self.thickness_plate,
        }

        self.getResults().setResults({'plate': plate,
                                      'prof': self.prof,
                                      'prof_c': self.prof_c})

        # getting data for drawings

        self.getResults().setResults({'draw_results': dnRigidBeamLib.get_draw_results(self.getItem(), self.which_column)})

        # region suche dane
        # dwuteownik = 1
        # self.prof = {'h': 270., 'tf': 10.2, 'r': 12., 'bfu': 100., 'bfd': 100., 'tw': 6.6, 'fy': 235., 'wpl': 460540.}
        if self.weld_type == trans(u'Pachwinowa'):
            aw = self.aw
        else:
            aw = 0.
        dis_w = plate['lp'] - 2. * self.dis_e  # miedzy kolumnami srub
        dis_m = (dis_w - self.prof['tw']) / 2. - 0.8*aw * 2 ** 0.5 # miedzy srodnikiem a srubami

        d = bolt_diameter[self.bolt_type][0]
        d0 = dnRigidBeamLib.calc_bolt_d0(self.bolt_type)
        dw = dnRigidBeamLib.bolt_size[self.bolt_type][0]  # srednica podkladki lub obrysu lba sruby lub nakretki
        As = bolt_diameter[self.bolt_type][1]
        fu_bolt = bolt_strength[self.bolt_class][1]

        beta_w = calc_beta_w(self.selected_steel, self.fu_plate)


        e1_column = 99999  # odl gornej sruby od konca slupa
        e4_column = 99999  # odl dolnej sruby od konca slupa

        E = 205000.
        GAMMA_M0 = get_gamma('M0')
        GAMMA_M1 = get_gamma('M1')
        GAMMA_M2 = get_gamma('M2')
        GAMMA_M3 = get_gamma('M3')

        wspolczynnik_kwc = 1  # 6.2.6.2(2)

        all_rows = self.bolts_above + self.bolts_under + self.rows_up + self.rows_down  # obliczenie ilosci rzedow srub

        FtRd = [0] * all_rows
        FvRd = [0] * all_rows
        h_od_polki_sciskanej = [0] * all_rows
        comb = {}

        Avc_column = self.prof_c['A'] - 2 * self.prof_c['bfu'] * self.prof_c['tf'] + \
                     (self.prof_c['tw'] + 2 * self.prof_c['r']) * self.prof_c['tf']

        # obliczanie odleglosci od rozciaganego konca blachy
        dis_bolt = [0] * all_rows  # odleglosci srub od poczatku blachy

        # endregion


        beam = self.getItem().getElements(node='both')[1 - self.which_column]
        if not soft:
            ord = dnRigidBeamLib.choose_node(beam, self.getItem())
            self._combination_data_USL = self._prepareCombinations(beam, ord,
                                                                   loadCombinationType=[
                                                                       sdConstants.LOAD_COMB_TYPE_USL_BASIC_EC,
                                                                       sdConstants.LOAD_COMB_TYPE_USL_SPECIAL_EC])


            #####################################################
            # get results obj

        r_obj = self.getResults()
        ratios_list = {k: [] for k in self.summarySubjects}
        shear_res_data = {}
        tension_res_data = {}
        bending_res_data = {}
        bending_tension_res_data = {}
        column_shear_res_data = {}
        weld_res_data = {}
        weld2_res_data = {}

        # THIS IS THE MAIN LOOP, here you perform calculations for every load combination
        for comb_data in self._combination_data_USL:

            # get your comb name and load groups
            comb_name = comb_data['name']
            load_groups = comb_data['load_groups']
            Mb1_Ed = comb_data['section_forces']['My'] * 1000000.      #Nmm
            Vb1_Ed = comb_data['section_forces']['Tz'] * 1000.          #N
            Nb1_Ed = comb_data['section_forces']['N'] * 1000.           #N
            Vc1_Ed = Nb1_Ed
            if self.column_on_right:
                Vc1_Ed = -Nb1_Ed
            Vc2_Ed = 0.
            Mb2_Ed = 0.

            # region welds calc
            if self.weld_type == trans(u'Pachwinowa'):
                weld_data = dnRigidBeamLib.calc_welds(self.prof, 0, aw, Nb1_Ed, Vb1_Ed, Mb1_Ed)
                sig_pros = weld_data['sig_pros']
                tauII = weld_data['tauII']
                z = weld_data['z']
                Aw = weld_data['Aw']
                sig_pros_resistance = dnRigidBeamLib.calc_sig_pros_resistance(self.fu_plate, GAMMA_M2)
                weld_resistance = dnRigidBeamLib.calc_weld_resistance(self.fu_plate, beta_w, GAMMA_M2)
                weld_ratio = math.sqrt(sig_pros ** 2 + 3 * (sig_pros ** 2 + tauII ** 2)) / weld_resistance
                weld2_ratio = sig_pros / sig_pros_resistance
                weld_comb_data = {
                    'loading': math.sqrt(sig_pros ** 2 + 3 * (sig_pros ** 2 + tauII ** 2)),
                    'resistance': weld_resistance,
                    'ratio': weld_ratio,
                    'sig_pros': sig_pros,
                    'tauII': tauII,
                    'z': z,
                    'Aw': Aw,
                    'load_groups': load_groups
                }
                weld_res_data[comb_name] = weld_comb_data
                weld2_comb_data = {
                    'loading': sig_pros,
                    'resistance': sig_pros_resistance,
                    'ratio': weld2_ratio,
                    'sig_pros': sig_pros,
                    'z': z,
                    'Aw': Aw,
                    'load_groups': load_groups
                }
                weld2_res_data[comb_name] = weld2_comb_data
                ratios_list[EXTREMAL_WELD_RATIO].append(weld_ratio)
                ratios_list[EXTREMAL_WELD2_RATIO].append(weld2_ratio)
            # endregion

            i = 0
            if Mb1_Ed < 0:
                if self.bolts_above:
                    odl = self.dis_m1 + e1
                    dis_bolt[i] = e1
                    i += 1
                    if self.rows_up:
                        dis_bolt[i] = self.dis_m1 + self.prof['tf'] + self.dis_p1 + dis_bolt[i - 1]
                        i += 1
                else:
                    odl = self.dis_m1
                    if self.rows_up:
                        dis_bolt[i] = self.dis_m1 + self.prof['tf'] + self.dis_p1
                        i += 1
                for _ in range(self.rows_up - 1):
                    dis_bolt[i] = dis_bolt[i - 1] + self.dis_p2
                    i += 1

                i = all_rows - 1
                if self.bolts_under:
                    odl2 = self.dis_m2 + e2
                    dis_bolt[i] = plate['hp'] - e2
                    i -= 1
                    if self.rows_down:
                        dis_bolt[i] = dis_bolt[i + 1] - self.dis_m2 - self.prof['tf'] - self.dis_p3
                        i -= 1
                else:
                    odl2 = self.dis_m2
                    if self.rows_down:
                        dis_bolt[i] = plate['hp'] - self.dis_m2 - self.prof['tf'] - self.dis_p3
                        i -= 1
                for _ in range(self.rows_down - 1):
                    dis_bolt[i] = dis_bolt[i + 1] - self.dis_p4
                    i -= 1
            else:
                if self.bolts_under:
                    odl2 = self.dis_m2 + e2
                    dis_bolt[i] = plate['hp'] - e2
                    i += 1
                    if self.rows_down:
                        dis_bolt[i] = dis_bolt[i - 1] - self.dis_m2 - self.prof['tf'] - self.dis_p3
                        i += 1
                else:
                    odl2 = self.dis_m2
                    if self.rows_down:
                        dis_bolt[i] = plate['hp'] - self.dis_m2 - self.prof['tf'] - self.dis_p3
                        i += 1
                for _ in range(self.rows_down - 1):
                    dis_bolt[i] = dis_bolt[i - 1] - self.dis_p4
                    i += 1
                i = all_rows - 1
                if self.bolts_above:
                    odl = self.dis_m1 + e1
                    dis_bolt[i] = e1
                    i -= 1
                    if self.rows_up:
                        dis_bolt[i] = self.dis_m1 + self.prof['tf'] + self.dis_p1 + dis_bolt[i + 1]
                        i -= 1
                else:
                    odl = self.dis_m1
                    if self.rows_up:
                        dis_bolt[i] = self.dis_m1 + self.prof['tf'] + self.dis_p1
                        i -= 1
                for _ in range(self.rows_up - 1):
                    dis_bolt[i] = dis_bolt[i + 1] + self.dis_p2
                    i -= 1

            # region test nowy

            bolt_in_shear_results = dnRigidBeamLib.bolt_in_shear(self.is_threaded, d, As, self.bolt_class,
                                                                 fu_bolt, GAMMA_M2)
            bolt_shear_resistance = bolt_in_shear_results['bolt_shear_resistance']
            # zerwanie sruby
            bolt_in_tension_results = dnRigidBeamLib.bolt_in_tension(fu_bolt, self.fu_plate, As, GAMMA_M2,
                                                                     self.bolt_type, plate['tp'])
            bolt_tension_resistance = bolt_in_tension_results['bolt_tension_resistance']
            plate_tension_resistance = bolt_in_tension_results['plate_tension_resistance']

            # nosnosci krocca teowego belki
            # nosnosc grup
            if self.rows_up + self.rows_down > 1:
                j = 0

                if Mb1_Ed < 0 and self.bolts_above == 1:
                    j = 1
                if Mb1_Ed > 0 and self.bolts_under == 1:
                    j = 1
                alpha = alpha_obliczenie(dis_m, dis_bolt[j] - odl - 0.5 * self.prof['tf'] - 0.8 * aw * 2 ** 0.5,
                                         self.dis_e)
                i = 1
                for _ in range(self.rows_up + self.rows_down - 1):
                    leffcp = math.pi * dis_m * 2. + 2. * (dis_bolt[i] - dis_bolt[j])
                    leff2 = (dis_bolt[i + j] - dis_bolt[j]) + dis_m * alpha
                    leff1 = min(leffcp, leff2)
                    comb['FtRd_grup_blach' + str(j + i)] = complete_yielding_of_end_plate_t_stub(
                        bolt_tension_resistance,
                        GAMMA_M0,
                        self.fy_plate, self.dis_m1 - 0.8 * aw * 2 ** 1 / 2,
                        self.dis_e, dw, plate['tp'],
                        leff1,
                        leff2, 2. * (i + 1))
                    comb['Ft_wb_Rd_grup' + str(j + i)] = {
                        'FtwbRd': srodnik_belki_rozciaganie(leff1, self.prof['tw'], self.prof['fy'], GAMMA_M0)}
                    i += 1

                i += 1
            # nosnosc 1 szeregu srub
            ktora_sruba = 0
            if Mb1_Ed < 0:
                if self.bolts_above == 1:
                    h_od_polki_sciskanej[ktora_sruba] = self.dis_m1 + self.prof['h'] - 0.5 * self.prof['tf']
                    leff = leff_1(self.dis_m1, dis_w, self.dis_e, self.dis_e, plate['lp'])
                    leff1 = leff['leff1']
                    leff2 = leff['leff2']
                    comb['FtRd_b' + str(ktora_sruba)] = complete_yielding_of_end_plate_t_stub(bolt_tension_resistance,
                                                                                              GAMMA_M0,
                                                                                              self.fy_plate,
                                                                                              self.dis_m1 - 0.8 * aw * 2 ** 1 / 2,
                                                                                              self.dis_e, dw,
                                                                                              plate['tp'], leff1,
                                                                                              leff2, 2)
                    ktora_sruba += 1
                if self.rows_up + self.rows_down > 0:
                    h_od_polki_sciskanej[ktora_sruba] =  self.prof['h'] + odl - 0.5*self.prof['tf'] - dis_bolt[
                            ktora_sruba]
                    alpha = alpha_obliczenie(dis_m, dis_bolt[ktora_sruba] - odl - self.prof['tf'] - 0.8 * aw * 2 ** 0.5,
                                             self.dis_e)
                    leff = leff_2(dis_m, alpha)
                    leff1 = leff['leff1']
                    leff2 = leff['leff2']
                    comb['FtRd_b' + str(ktora_sruba)] = complete_yielding_of_end_plate_t_stub(bolt_tension_resistance,
                                                                                              GAMMA_M0,
                                                                                              self.fy_plate,
                                                                                              dis_m,
                                                                                              self.dis_e, dw,
                                                                                              plate['tp'], leff1,
                                                                                              leff2, 2)
                    comb['Ft_wb_Rd' + str(ktora_sruba)] = {
                        'FtwbRd': srodnik_belki_rozciaganie(leff1, self.prof['tw'], self.prof['fy'], GAMMA_M0)}
                    ktora_sruba += + 1
                    for _ in range(self.rows_up + self.rows_down - 1):
                        h_od_polki_sciskanej[ktora_sruba] = self.prof['h'] + odl - 0.5*self.prof['tf'] - dis_bolt[
                            ktora_sruba]
                        leff = leff_3(dis_m, self.dis_e)
                        leff1 = leff['leff1']
                        leff2 = leff['leff2']
                        comb['FtRd_b' + str(ktora_sruba)] = complete_yielding_of_end_plate_t_stub(
                            bolt_tension_resistance, GAMMA_M0,
                            self.fy_plate,
                            dis_m,
                            self.dis_e, dw, plate['tp'],
                            leff1, leff2, 2)
                        comb['Ft_wb_Rd' + str(ktora_sruba)] = {
                            'FtwbRd': srodnik_belki_rozciaganie(leff1, self.prof['tw'], self.prof['fy'], GAMMA_M0)}
                        ktora_sruba += 1
                if self.bolts_under == 1:
                    h_od_polki_sciskanej[ktora_sruba] = 0.
                    leff = leff_3(self.dis_m2, e2)
                    leff1 = leff['leff1']
                    leff2 = leff['leff2']
                    comb['FtRd_b' + str(ktora_sruba)] = complete_yielding_of_end_plate_t_stub(bolt_tension_resistance,
                                                                                              GAMMA_M0,
                                                                                              self.fy_plate,
                                                                                              self.dis_m1 - 0.8 * aw * 2 ** 1 / 2,
                                                                                              self.dis_e, dw,
                                                                                              plate['tp'],
                                                                                              leff1, leff2, 2)
            else:
                if self.bolts_under == 1:
                    h_od_polki_sciskanej[ktora_sruba] = self.dis_m2 + self.prof['h'] - 0.5 * self.prof['tf']
                    leff = leff_1(self.dis_m2, dis_w, self.dis_e, e2, plate['lp'])
                    leff1 = leff['leff1']
                    leff2 = leff['leff2']
                    comb['FtRd_b' + str(ktora_sruba)] = complete_yielding_of_end_plate_t_stub(bolt_tension_resistance,
                                                                                              GAMMA_M0,
                                                                                              self.fy_plate,
                                                                                              self.dis_m1 - 0.8 * aw * 2 ** 1 / 2,
                                                                                              self.dis_e, dw,
                                                                                              plate['tp'], leff1,
                                                                                              leff2, 2)
                    ktora_sruba += 1
                if self.rows_up + self.rows_down > 0:
                    h_od_polki_sciskanej[ktora_sruba] = dis_bolt[ktora_sruba] - odl - 0.5 * self.prof['tf']
                    alpha = alpha_obliczenie(dis_m,
                                             self.prof['h'] - dis_bolt[ktora_sruba] + odl2 + self.prof[
                                                 'tf'] - 0.8 * aw * 2 ** 0.5,
                                             self.dis_e)
                    leff = leff_2(dis_m, alpha)
                    leff1 = leff['leff1']
                    leff2 = leff['leff2']
                    comb['FtRd_b' + str(ktora_sruba)] = complete_yielding_of_end_plate_t_stub(bolt_tension_resistance,
                                                                                              GAMMA_M0,
                                                                                              self.fy_plate,
                                                                                              dis_m,
                                                                                              self.dis_e, dw,
                                                                                              plate['tp'], leff1,
                                                                                              leff2, 2)
                    comb['Ft_wb_Rd' + str(ktora_sruba)] = {
                        'FtwbRd': srodnik_belki_rozciaganie(leff1, self.prof['tw'], self.prof['fy'], GAMMA_M0)}
                    ktora_sruba += 1
                    for _ in range(self.rows_up + self.rows_down - 1):
                        h_od_polki_sciskanej[ktora_sruba] = dis_bolt[ktora_sruba] - odl - 0.5 * self.prof['tf']
                        leff = leff_3(dis_m, self.dis_e)
                        leff1 = leff['leff1']
                        leff2 = leff['leff2']
                        comb['FtRd_b' + str(ktora_sruba)] = complete_yielding_of_end_plate_t_stub(
                            bolt_tension_resistance, GAMMA_M0,
                            self.fy_plate,dis_m,
                            self.dis_e, dw, plate['tp'],
                            leff1, leff2, 2)
                        comb['Ft_wb_Rd' + str(ktora_sruba)] = {
                            'FtwbRd': srodnik_belki_rozciaganie(leff1, self.prof['tw'], self.prof['fy'], GAMMA_M0)}
                        ktora_sruba += 1
                if self.bolts_above == 1:
                    h_od_polki_sciskanej[ktora_sruba] = 0.
                    leff = leff_3(self.dis_m1, self.dis_e)
                    leff1 = leff['leff1']
                    leff2 = leff['leff2']
                    comb['FtRd_b' + str(ktora_sruba)] = complete_yielding_of_end_plate_t_stub(bolt_tension_resistance,
                                                                                              GAMMA_M0,
                                                                                              self.fy_plate,
                                                                                              self.dis_m1 - 0.8 * aw * 2 ** 1 / 2,
                                                                                              self.dis_e, dw,
                                                                                              plate['tp'],
                                                                                              leff1, leff2, 2)
            # region slup

            if self.connection_type == CONNECTION_BEAM_TO_COLUMN:
                # obliczenie ramienia dzwigni
                if h_od_polki_sciskanej[1] < 0:
                    z_ramie_dzwigni = h_od_polki_sciskanej[0]
                else:
                    z_ramie_dzwigni = (h_od_polki_sciskanej[0] + h_od_polki_sciskanej[1]) / 2
                # Panel srodnika slupa w warunkach scinania
                comb['psswws'] = psswws = {'VwpRd': panel_srodnika_scinanie(Avc_column, self.prof_c['fy'], GAMMA_M0),
                                           'VwpEd': (Mb1_Ed - Mb2_Ed) / z_ramie_dzwigni - (Vc1_Ed - Vc2_Ed) / 2}
                # srodnik slupa w strefie poprzecznego sciskania
                c = (plate['hp'] - self.prof['h'])/2
                if c < 0:
                    c = 0
                comb['sswsps'] = sswsps = {
                    'beffcwc': szerokosc_efektywna_srodnika_slupa_przy_sciskaniu(plate['tp'], c, self.prof['tf'],
                                                                                 aw,
                                                                                 self.prof_c['tf'],
                                                                                 self.prof_c['r']), }
                comb['sswsps']['omega'] = obliczenie_wspolczynnika_redukcyjnego_interakcji_ze_scinaniem(
                    comb['sswsps']['beffcwc'],
                    self.prof_c['tw'], Avc_column)
                comb['sswsps']['ro'] = obliczenie_wspolczynnika_wyboczenia(comb['sswsps']['beffcwc'], self.prof_c['tf'],
                                                                           self.prof_c['r'],
                                                                           self.prof_c['h'],
                                                                           self.prof_c['fy'], E, self.prof_c['tw'])
                comb['sswsps']['FcwcRd'] = srodnik_przy_sciskaniu(comb['sswsps']['omega'], wspolczynnik_kwc,
                                                                  comb['sswsps']['beffcwc'], self.prof_c['tw'],
                                                                  self.prof_c['fy'],
                                                                  GAMMA_M0, GAMMA_M1, comb['sswsps']['ro'])
                # Pas i srodnik belki w strefie sciskanej

                comb['pisbwss'] = {'McRd': nosnosc_na_zginanie(self.prof['wpl'], self.prof['fy'], GAMMA_M0)}
                comb['pisbwss']['FcfbRd'] = pas_i_srodnik_przy_sciskaniu(comb['pisbwss']['McRd'], self.prof['h'],
                                                                         self.prof['tf'])
                # strefa rozciagana
                m = (dis_w - self.prof_c['tw']) / 2 - 0.8 * self.prof_c['r']
                e = (self.prof_c['bfu'] - dis_w) / 2

                leff = leff_6(m, e, e1_column)
                leff1 = leff['leff1']
                leff2 = leff['leff2']
                if Mb1_Ed < 0:
                    comb['FtRd_c_1'] = complete_yielding_of_end_plate_t_stub(bolt_tension_resistance, GAMMA_M0,
                                                                             self.prof_c['fy'], m,
                                                                             min(e, self.dis_e), dw, self.prof_c['tf'],
                                                                             leff1, leff2, 2)
                    comb['sswspr_1'] = {
                        'omega': obliczenie_wspolczynnika_redukcyjnego_interakcji_ze_scinaniem(leff1, self.prof_c['tw'],
                                                                                               Avc_column)}
                    comb['sswspr_1']['FtwcRd'] = srodnik_przy_rozciaganiu(comb['sswspr_1']['omega'], leff1,
                                                                          self.prof_c['tw'],
                                                                          self.prof_c['fy'], GAMMA_M0)
                else:
                    comb['FtRd_c_n'] = complete_yielding_of_end_plate_t_stub(bolt_tension_resistance, GAMMA_M0,
                                                                             self.prof_c['fy'], m,
                                                                             min(e, self.dis_e), dw, self.prof_c['tf'],
                                                                             leff1, leff2, 2)
                    comb['sswspr_n'] = {
                        'omega': obliczenie_wspolczynnika_redukcyjnego_interakcji_ze_scinaniem(leff1, self.prof_c['tw'],
                                                                                               Avc_column)}
                    comb['sswspr_n']['FtwcRd'] = srodnik_przy_rozciaganiu(comb['sswspr_n']['omega'], leff1,
                                                                          self.prof_c['tw'],
                                                                          self.prof_c['fy'], GAMMA_M0)
                leff = leff_5(m, e)
                leff1 = leff['leff1']
                leff2 = leff['leff2']
                comb['FtRd_c_middle'] = complete_yielding_of_end_plate_t_stub(bolt_tension_resistance, GAMMA_M0,
                                                                              self.prof_c['fy'], m, min(e, self.dis_e),
                                                                              dw, self.prof_c['tf'], leff1, leff2, 2)
                comb['sswspr_middle'] = {
                    'omega': obliczenie_wspolczynnika_redukcyjnego_interakcji_ze_scinaniem(leff1, self.prof_c['tw'],
                                                                                           Avc_column)}
                comb['sswspr_middle']['FtwcRd'] = srodnik_przy_rozciaganiu(comb['sswspr_middle']['omega'], leff1,
                                                                           self.prof_c['tw'],
                                                                           self.prof_c['fy'], GAMMA_M0)
                leff = leff_6(m, e, e4_column)
                leff1 = leff['leff1']
                leff2 = leff['leff2']
                if Mb1_Ed < 0:
                    comb['FtRd_c_n'] = complete_yielding_of_end_plate_t_stub(bolt_tension_resistance, GAMMA_M0,
                                                                             self.prof_c['fy'], m,
                                                                             min(e, self.dis_e), dw, self.prof_c['tf'],
                                                                             leff1, leff2, 2)
                    comb['sswspr_n'] = {
                        'omega': obliczenie_wspolczynnika_redukcyjnego_interakcji_ze_scinaniem(leff1, self.prof_c['tw'],
                                                                                               Avc_column)}
                    comb['sswspr_n']['FtwcRd'] = srodnik_przy_rozciaganiu(comb['sswspr_n']['omega'], leff1,
                                                                          self.prof_c['tw'],
                                                                          self.prof_c['fy'], GAMMA_M0)
                else:
                    comb['FtRd_c_1'] = complete_yielding_of_end_plate_t_stub(bolt_tension_resistance, GAMMA_M0,
                                                                             self.prof_c['fy'], m,
                                                                             min(e, self.dis_e), dw, self.prof_c['tf'],
                                                                             leff1, leff2, 2)
                    comb['sswspr_1'] = {
                        'omega': obliczenie_wspolczynnika_redukcyjnego_interakcji_ze_scinaniem(leff1, self.prof_c['tw'],
                                                                                               Avc_column)}
                    comb['sswspr_1']['FtwcRd'] = srodnik_przy_rozciaganiu(comb['sswspr_1']['omega'], leff1,
                                                                          self.prof_c['tw'],
                                                                          self.prof_c['fy'], GAMMA_M0)
                # grupy
                j = 0
                if Mb1_Ed > 0 and self.bolts_above == 1:
                    j = 1
                if Mb1_Ed < 0 and self.bolts_under == 1:
                    j = 1
                i = 1
                pom1 = min(math.pi * m, 2 * e1_column)
                pom2 = min(2 * m + 0.625 * e, e1_column)
                pom3 = min(math.pi * m, 2 * e4_column)
                pom4 = min(2 * m + 0.625 * e, e4_column)
                if Mb1_Ed < 0:
                    for _ in range(all_rows - 1 - j):
                        leffcp = pom1 + (dis_bolt[i] - dis_bolt[0]) / i * (2 * i + 1)
                        leff2 = pom2 + (dis_bolt[i] - dis_bolt[0]) / 2 / i * (2 * i + 1)
                        leff1 = min(leffcp, leff2)
                        comb['FtRd_grup_slup' + str(i)] = complete_yielding_of_end_plate_t_stub(bolt_tension_resistance,
                                                                                                GAMMA_M0,
                                                                                                self.fy_plate,
                                                                                                self.dis_m1 - 0.8 * aw * 2 ** 1 / 2,
                                                                                                self.dis_e, dw,
                                                                                                plate['tp'], leff1,
                                                                                                leff2, 2 * (i + 1))
                        comb['sswspr_grupy' + str(i)] = {
                            'omega': obliczenie_wspolczynnika_redukcyjnego_interakcji_ze_scinaniem(leff1, self.prof_c['tw'],
                                                                                                   Avc_column)}
                        comb['sswspr_grupy' + str(i)]['FtwcRd'] = srodnik_przy_rozciaganiu(
                            comb['sswspr_grupy' + str(i)]['omega'],
                            leff1,
                            self.prof_c['tw'],
                            self.prof_c['fy'], GAMMA_M0)
                        i += 1
                else:
                    for _ in range(all_rows - 1 - j):
                        leffcp = pom2 + abs(dis_bolt[i] - dis_bolt[0]) / i * (2 * i + 1)
                        leff2 = pom3 + abs(dis_bolt[i] - dis_bolt[0]) / 2 / i * (2 * i + 1)
                        leff1 = min(leffcp, leff2)
                        comb['FtRd_grup_slup' + str(i)] = complete_yielding_of_end_plate_t_stub(bolt_tension_resistance,
                                                                                                GAMMA_M0,
                                                                                                self.fy_plate,
                                                                                                self.dis_m1 - 0.8 * aw * 2 ** 1 / 2,
                                                                                                self.dis_e, dw,
                                                                                                plate['tp'], leff1,
                                                                                                leff2, 2 * (i + 1))
                        comb['sswspr_grupy' + str(i)] = {
                            'omega': obliczenie_wspolczynnika_redukcyjnego_interakcji_ze_scinaniem(leff1, self.prof_c['tw'],
                                                                                                   Avc_column)}
                        comb['sswspr_grupy' + str(i)]['FtwcRd'] = srodnik_przy_rozciaganiu(
                            comb['sswspr_grupy' + str(i)]['omega'],
                            leff1,
                            self.prof_c['tw'],
                            self.prof_c['fy'], GAMMA_M0)
                        i += 1

            # endregion

            # scinanie 1 rzad
            ktora_sruba = 0
            # docisk srub do blachy
            j = 0
            if Mb1_Ed < 0 and self.bolts_above == 1:
                j = 1
            if Mb1_Ed > 0 and self.bolts_under == 1:
                j = 1
            if j > 0:
                if Mb1_Ed < 0:
                    comb['bearing_p' + str(ktora_sruba)] = bolt_bearing(e1, self.dis_e, d, d0, plate['tp'],
                                                                        GAMMA_M2, fu_bolt,
                                                                        self.fu_plate)
                else:
                    comb['bearing_p' + str(ktora_sruba)] = bolt_bearing(e2,
                                                                        self.dis_e, d, d0, plate['tp'], GAMMA_M2,
                                                                        fu_bolt,
                                                                        self.fu_plate)
            else:
                if Mb1_Ed < 0:
                    comb['bearing_p' + str(ktora_sruba)] = bolt_bearing(self.dis_m1 + self.dis_p1 + self.prof['tf'],
                                                                        self.dis_e, d, d0, plate['tp'],
                                                                        GAMMA_M2, fu_bolt,
                                                                        self.fu_plate)
                else:
                    comb['bearing_p' + str(ktora_sruba)] = bolt_bearing(self.dis_m2 + self.dis_p2 + self.prof['tf'],
                                                                        self.dis_e, d, d0, plate['tp'], GAMMA_M2,
                                                                        fu_bolt,
                                                                        self.fu_plate)
            ktora_sruba = 1
            for _ in range(all_rows - 2):
                comb['bearing_p' + str(ktora_sruba)] = bolt_bearing2(
                    min(abs(dis_bolt[ktora_sruba - 1] - dis_bolt[ktora_sruba - 2]),
                        abs(dis_bolt[ktora_sruba] - dis_bolt[ktora_sruba - 1])),
                    self.dis_e, d, d0, plate['tp'], GAMMA_M2, fu_bolt,
                    self.fu_plate)
                ktora_sruba += 1

                if Mb1_Ed < 0:
                    comb['bearing_p' + str(ktora_sruba)] = bolt_bearing(e2, self.dis_e, d, d0, plate['tp'],
                                                                        GAMMA_M2, fu_bolt,
                                                                        self.fu_plate)
                else:
                    comb['bearing_p' + str(ktora_sruba)] = bolt_bearing(e1,
                                                                        self.dis_e, d, d0, plate['tp'], GAMMA_M2,
                                                                        fu_bolt,
                                                                        self.fu_plate)
            else:
                if Mb1_Ed < 0:
                    comb['bearing_p' + str(ktora_sruba)] = bolt_bearing(self.dis_m2 + self.dis_p2 + self.prof['tf'],
                                                                        self.dis_e, d, d0, plate['tp'],
                                                                        GAMMA_M2, fu_bolt,
                                                                        self.fu_plate)
                else:
                    comb['bearing_p' + str(ktora_sruba)] = bolt_bearing(self.dis_m1 + self.dis_p1 + self.prof['tf'],
                                                                        self.dis_e, d, d0, plate['tp'], GAMMA_M2,
                                                                        fu_bolt,
                                                                        self.fu_plate)

            # region docisk do slupa
            ktora_sruba = 0
            if self.connection_type == CONNECTION_BEAM_TO_COLUMN:
                if Mb1_Ed < 0:
                    comb['bearing_c' + str(ktora_sruba)] = bolt_bearing(e1_column, self.dis_e, d, d0, plate['tp'],
                                                                        GAMMA_M2, fu_bolt,
                                                                        self.fu_plate)
                else:
                    comb['bearing_c' + str(ktora_sruba)] = bolt_bearing(e4_column,
                                                                        self.dis_e, d, d0, plate['tp'], GAMMA_M2,
                                                                        fu_bolt,
                                                                        self.fu_plate)
                ktora_sruba = 1
                for _ in range(all_rows - 2):
                    comb['bearing_c' + str(ktora_sruba)] = bolt_bearing2(
                        min(abs(dis_bolt[ktora_sruba - 1] - dis_bolt[ktora_sruba - 2]),
                            abs(dis_bolt[ktora_sruba] - dis_bolt[ktora_sruba - 1])),
                        self.dis_e, d, d0, plate['tp'], GAMMA_M2, fu_bolt,
                        self.fu_plate)
                    ktora_sruba += 1
                if Mb1_Ed < 0:
                    comb['bearing_c' + str(ktora_sruba)] = bolt_bearing(e1_column, self.dis_e, d, d0, plate['tp'],
                                                                        GAMMA_M2, fu_bolt,
                                                                        self.fu_plate)
                else:
                    comb['bearing_c' + str(ktora_sruba)] = bolt_bearing(e4_column,
                                                                        self.dis_e, d, d0, plate['tp'], GAMMA_M2,
                                                                        fu_bolt,
                                                                        self.fu_plate)
            # endregion


            # obliczanie FtRd
            j = 0

            if Mb1_Ed < 0 and self.bolts_above == 1:
                j = 1
            if Mb1_Ed > 0 and self.bolts_under == 1:
                j = 1
            Fpom1 = 0
            Fpom2 = 0
            ktora_sruba = 0
            if self.connection_type == CONNECTION_BEAM_TO_COLUMN:
                if j > 0:
                    FtRd[0] = min(comb['FtRd_b' + str(ktora_sruba)]['FtRd'],
                                  comb['FtRd_c_1']['FtRd'],
                                  comb['psswws']['VwpRd'],
                                  comb['sswspr_1']['FtwcRd'],
                                  comb['pisbwss']['FcfbRd'],
                                  comb['sswsps']['FcwcRd'],
                                  )
                    FtRdmax = FtRd[0]
                    FtRdmax_h = FtRd[0] / h_od_polki_sciskanej[0]
                    Fpom1 += FtRd[0]
                    ktora_sruba += 1
                    if self.rows_up + self.rows_down > 0:
                        FtRd[1] = min(comb['FtRd_b' + str(ktora_sruba)]['FtRd'],
                                      comb['Ft_wb_Rd' + str(ktora_sruba)]['FtwbRd'],
                                      comb['FtRd_c_middle']['FtRd'],
                                      comb['sswspr_middle']['FtwcRd'],
                                      comb['FtRd_grup_slup' + str(ktora_sruba)]['FtRd'] - Fpom1,
                                      comb['sswspr_grupy' + str(ktora_sruba)]['FtwcRd'] - Fpom1,
                                      comb['psswws']['VwpRd'] - Fpom1,
                                      comb['pisbwss']['FcfbRd'] - Fpom1,
                                      comb['sswsps']['FcwcRd'] - Fpom1,
                                      )
                        if FtRd[1] > FtRdmax:
                            FtRdmax = FtRd[1]
                            FtRdmax_h = FtRd[1] / h_od_polki_sciskanej[1]
                        if FtRdmax > 1.9 * FtRd[1]:
                            FtRd[1] = FtRdmax_h * h_od_polki_sciskanej[1]
                        Fpom1 += FtRd[1]
                        Fpom2 += FtRd[1]
                        ktora_sruba += 1
                    for _ in range(self.rows_up + self.rows_down - 1):
                        FtRd[ktora_sruba] = min(comb['FtRd_b' + str(ktora_sruba)]['FtRd'],
                                                comb['Ft_wb_Rd' + str(ktora_sruba)]['FtwbRd'],
                                                comb['Ft_wb_Rd_grup' + str(ktora_sruba)]['FtwbRd'] - Fpom2,
                                                comb['FtRd_grup_blach' + str(ktora_sruba)]['FtRd'] - Fpom2,
                                                comb['FtRd_c_middle']['FtRd'],
                                                comb['sswspr_middle']['FtwcRd'],
                                                comb['FtRd_grup_slup' + str(ktora_sruba)]['FtRd'] - Fpom1,
                                                comb['sswspr_grupy' + str(ktora_sruba)]['FtwcRd'] - Fpom1,
                                                comb['psswws']['VwpRd'] - Fpom1,
                                                comb['pisbwss']['FcfbRd'] - Fpom1,
                                                comb['sswsps']['FcwcRd'] - Fpom1,
                                                )
                        if FtRd[ktora_sruba] > FtRdmax:
                            FtRdmax = FtRd[ktora_sruba]
                            FtRdmax_h = FtRd[ktora_sruba] / h_od_polki_sciskanej[ktora_sruba]
                        if FtRdmax > 1.9 * FtRd[ktora_sruba]:
                            FtRd[ktora_sruba] = FtRdmax_h * h_od_polki_sciskanej[ktora_sruba]
                        Fpom1 += FtRd[ktora_sruba]
                        Fpom2 += FtRd[ktora_sruba]
                        ktora_sruba += 1
                    if self.bolts_above + self.bolts_under == 2:
                        FtRd[all_rows - 1] = min(
                            comb['FtRd_b' + str(ktora_sruba)]['FtRd'],
                            comb['FtRd_c_n']['FtRd'],
                            comb['psswws']['VwpRd'],
                            comb['sswspr_n']['FtwcRd'],
                            comb['pisbwss']['FcfbRd'],
                            comb['sswsps']['FcwcRd']
                        )
                        if FtRdmax > 1.9 * FtRd[all_rows - 1]:
                            FtRd[all_rows - 1] = FtRdmax_h * h_od_polki_sciskanej[all_rows - 1]
                else:

                    FtRd[0] = min(comb['FtRd_b' + str(ktora_sruba)]['FtRd'],
                                  comb['Ft_wb_Rd' + str(ktora_sruba)]['FtwbRd'],
                                  comb['FtRd_c_1']['FtRd'],
                                  comb['sswspr_1']['FtwcRd'],
                                  comb['psswws']['VwpRd'],
                                  comb['pisbwss']['FcfbRd'],
                                  comb['sswsps']['FcwcRd'],
                                  )
                    FtRdmax = FtRd[0]
                    FtRdmax_h = FtRd[0] / h_od_polki_sciskanej[0]
                    Fpom1 += FtRd[0]
                    Fpom2 += FtRd[0]
                    ktora_sruba += 1
                    for _ in range(self.rows_up + self.rows_down - 1):
                        FtRd[ktora_sruba] = min(comb['FtRd_b' + str(ktora_sruba)]['FtRd'],
                                                comb['Ft_wb_Rd' + str(ktora_sruba)]['FtwbRd'],
                                                comb['Ft_wb_Rd_grup' + str(ktora_sruba)]['FtwbRd'] - Fpom2,
                                                comb['FtRd_grup_blach' + str(ktora_sruba)]['FtRd'] - Fpom2,
                                                comb['FtRd_c_middle']['FtRd'],
                                                comb['sswspr_middle']['FtwcRd'],
                                                comb['FtRd_grup_slup' + str(ktora_sruba)]['FtRd'] - Fpom1,
                                                comb['sswspr_grupy' + str(ktora_sruba)]['FtwcRd'] - Fpom1,
                                                comb['psswws']['VwpRd'] - Fpom1,
                                                comb['pisbwss']['FcfbRd'] - Fpom1,
                                                comb['sswsps']['FcwcRd'] - Fpom1,
                                                )
                        if FtRd[ktora_sruba] > FtRdmax:
                            FtRdmax = FtRd[ktora_sruba]
                            FtRdmax_h = FtRd[ktora_sruba] / h_od_polki_sciskanej[ktora_sruba]
                        if FtRdmax > 1.9 * FtRd[ktora_sruba]:
                            FtRd[ktora_sruba] = FtRdmax_h * h_od_polki_sciskanej[ktora_sruba]
                        Fpom1 += FtRd[ktora_sruba]
                        Fpom2 += FtRd[ktora_sruba]
                        ktora_sruba += 1
                    if self.bolts_above + self.bolts_under == 1:
                        FtRd[all_rows - 1] = min(
                            comb['FtRd_b' + str(ktora_sruba)]['FtRd'],
                            comb['FtRd_c_n']['FtRd'],
                            comb['psswws']['VwpRd'],
                            comb['sswspr_n']['FtwcRd'],
                            comb['pisbwss']['FcfbRd'],
                            comb['sswsps']['FcwcRd']
                        )
                        if FtRdmax > 1.9 * FtRd[all_rows - 1]:
                            FtRd[all_rows - 1] = FtRdmax_h * h_od_polki_sciskanej[all_rows - 1]
            else:
                if j > 0:
                    FtRd[0] = comb['FtRd_b' + str(ktora_sruba)]['FtRd']
                    FtRdmax = FtRd[0]
                    FtRdmax_h = FtRd[0] / h_od_polki_sciskanej[0]
                    Fpom1 += FtRd[0]
                    ktora_sruba += 1
                    if self.rows_up + self.rows_down > 0:
                        FtRd[1] = min(comb['FtRd_b' + str(ktora_sruba)]['FtRd'],
                                      comb['Ft_wb_Rd' + str(ktora_sruba)]['FtwbRd'],
                                      )
                        if FtRd[1] > FtRdmax:
                            FtRdmax = FtRd[1]
                            FtRdmax_h = FtRd[1] / h_od_polki_sciskanej[1]
                        if FtRdmax > 1.9 * FtRd[1]:
                            FtRd[1] = FtRdmax_h * h_od_polki_sciskanej[1]
                        Fpom1 += FtRd[1]
                        Fpom2 += FtRd[1]
                        ktora_sruba += 1
                    for _ in range(self.rows_up + self.rows_down - 1):
                        FtRd[ktora_sruba] = min(comb['FtRd_b' + str(ktora_sruba)]['FtRd'],
                                                comb['Ft_wb_Rd' + str(ktora_sruba)]['FtwbRd'],
                                                comb['Ft_wb_Rd_grup' + str(ktora_sruba)]['FtwbRd'] - Fpom2,
                                                comb['FtRd_grup_blach' + str(ktora_sruba)]['FtRd'] - Fpom2,
                                                )
                        if FtRd[ktora_sruba] > FtRdmax:
                            FtRdmax = FtRd[ktora_sruba]
                            FtRdmax_h = FtRd[ktora_sruba] / h_od_polki_sciskanej[ktora_sruba]
                        if FtRdmax > 1.9 * FtRd[ktora_sruba]:
                            FtRd[ktora_sruba] = FtRdmax_h * h_od_polki_sciskanej[ktora_sruba]
                        Fpom1 += FtRd[ktora_sruba]
                        Fpom2 += FtRd[ktora_sruba]
                        ktora_sruba += 1
                    if self.bolts_above + self.bolts_under == 2:
                        FtRd[all_rows - 1] = comb['FtRd_b' + str(ktora_sruba)]['FtRd']
                        if FtRdmax > 1.9 * FtRd[all_rows - 1]:
                            FtRd[all_rows - 1] = FtRdmax_h * h_od_polki_sciskanej[all_rows - 1]
                else:

                    FtRd[0] = min(comb['FtRd_b' + str(ktora_sruba)]['FtRd'],
                                  comb['Ft_wb_Rd' + str(ktora_sruba)]['FtwbRd'],
                                  )
                    FtRdmax = FtRd[0]
                    FtRdmax_h = FtRd[0] / h_od_polki_sciskanej[0]
                    Fpom1 += FtRd[0]
                    Fpom2 += FtRd[0]
                    ktora_sruba += 1
                    for _ in range(self.rows_up + self.rows_down - 1):
                        FtRd[ktora_sruba] = min(comb['FtRd_b' + str(ktora_sruba)]['FtRd'],
                                                comb['Ft_wb_Rd' + str(ktora_sruba)]['FtwbRd'],
                                                comb['Ft_wb_Rd_grup' + str(ktora_sruba)]['FtwbRd'] - Fpom2,
                                                comb['FtRd_grup_blach' + str(ktora_sruba)]['FtRd'] - Fpom2,
                                                )
                        if FtRd[ktora_sruba] > FtRdmax:
                            FtRdmax = FtRd[ktora_sruba]
                            FtRdmax_h = FtRd[ktora_sruba] / h_od_polki_sciskanej[ktora_sruba]
                        if FtRdmax > 1.9 * FtRd[ktora_sruba]:
                            FtRd[ktora_sruba] = FtRdmax_h * h_od_polki_sciskanej[ktora_sruba]
                        Fpom1 += FtRd[ktora_sruba]
                        Fpom2 += FtRd[ktora_sruba]
                        ktora_sruba += 1
                    if self.bolts_above + self.bolts_under == 1:
                        FtRd[all_rows - 1] = comb['FtRd_b' + str(ktora_sruba)]['FtRd']
                        if FtRdmax > 1.9 * FtRd[all_rows - 1]:
                            FtRd[all_rows - 1] = FtRdmax_h * h_od_polki_sciskanej[all_rows - 1]

            # obliczanie FvRd
            ktora_sruba = 0
            if self.connection_type == CONNECTION_BEAM_TO_COLUMN:
                for _ in range(all_rows):
                    if h_od_polki_sciskanej[ktora_sruba] > 0:
                        FvRd[ktora_sruba] = min(comb['bearing_c' + str(ktora_sruba)]['bolt_bearing_resistance'],
                                                comb['bearing_p' + str(ktora_sruba)]['bolt_bearing_resistance'],
                                                bolt_in_shear_results['bolt_shear_resistance']
                                                ) * 0.4 / 1.4
                        ktora_sruba += 1
                    else:
                        FvRd[ktora_sruba] = min(comb['bearing_c' + str(ktora_sruba)]['bolt_bearing_resistance'],
                                                comb['bearing_p' + str(ktora_sruba)]['bolt_bearing_resistance'],
                                                bolt_in_shear_results['bolt_shear_resistance']
                                                )
                        ktora_sruba += 1
            else:
                for _ in range(all_rows):
                    if h_od_polki_sciskanej[ktora_sruba] > 0:
                        FvRd[ktora_sruba] = min(comb['bearing_p' + str(ktora_sruba)]['bolt_bearing_resistance'],
                                                bolt_in_shear_results['bolt_shear_resistance']
                                                ) * 0.4 / 1.4
                        ktora_sruba += 1
                    else:
                        FvRd[ktora_sruba] = min(comb['bearing_p' + str(ktora_sruba)]['bolt_bearing_resistance'],
                                                bolt_in_shear_results['bolt_shear_resistance']
                                                )
                        ktora_sruba += 1
            MRd = 0
            NRd = 0
            VRd = 0
            i = 0
            for _ in range(all_rows):
                MRd += FtRd[i] * h_od_polki_sciskanej[i]
                VRd += FvRd[i]
                if h_od_polki_sciskanej[i] > 0:
                    NRd += FtRd[i]
                i += 1

            # endregion

            print(comb)
            Vb1_Ed = abs(Vb1_Ed) / 1000.  # kN
            Nb1_Ed = abs(Nb1_Ed) / 1000.  # kN
            Mb1_Ed = abs(Mb1_Ed) / 1000000.  # kNm
            VRd = abs(VRd) / 1000.  # kN
            NRd = abs(NRd) / 1000.  # kN
            MRd = abs(MRd) / 1000000.  # kNm
            if self.connection_type == CONNECTION_BEAM_TO_COLUMN:
                VwpEd = abs(comb['psswws']['VwpEd']) / 1000. #kN
                VwpRd = abs(comb['psswws']['VwpRd']) / 1000. #kN

            shear_comb_data = {
                'loading': Vb1_Ed,
                'resistance': VRd,
                'ratio': Vb1_Ed / VRd,
            }
            shear_res_data[comb_name] = shear_comb_data
            ratios_list[EXTREMAL_SHEAR_RATIO].append(Vb1_Ed / VRd)

            tension_comb_data = {
                'loading': Nb1_Ed,
                'resistance': NRd,
                'ratio': Nb1_Ed / NRd,
            }
            tension_res_data[comb_name] = tension_comb_data
            ratios_list[EXTREMAL_TENSION_RATIO].append(Nb1_Ed / NRd)

            bending_comb_data = {
                'loading': Mb1_Ed,
                'resistance': MRd,
                'ratio': Mb1_Ed / MRd,
            }
            bending_res_data[comb_name] = bending_comb_data
            ratios_list[EXTREMAL_BENDING_RATIO].append(Mb1_Ed / MRd)

            bending_tension_comb_data = {
                'resistance1': Mb1_Ed / MRd,
                'resistance2': Nb1_Ed / NRd,
                'ratio': Mb1_Ed / MRd + Nb1_Ed / NRd,
            }
            bending_tension_res_data[comb_name] = bending_tension_comb_data
            ratios_list[EXTREMAL_BENDING_TENSION_RATIO].append(Mb1_Ed / MRd + Nb1_Ed / NRd)

            if self.connection_type == CONNECTION_BEAM_TO_COLUMN:
                column_shear_comb_data = {
                    'loading': VwpEd,
                    'resistance': VwpRd,
                    'ratio': VwpEd/VwpRd,
                }
                column_shear_res_data[comb_name] = column_shear_comb_data
                ratios_list[EXTREMAL_COLUMN_SHEAR_RATIO].append(Nb1_Ed / NRd)

        # you went through all combs, now collect data for all conditions
        result_data = {}
        ratio_data = {}

        if self.weld_type == trans(u'Pachwinowa'):
            ratio_data[EXTREMAL_WELD_RATIO] = max(ratios_list[EXTREMAL_WELD_RATIO])
            result_data[EXTREMAL_WELD_RATIO] = weld_res_data

            ratio_data[EXTREMAL_WELD2_RATIO] = max(ratios_list[EXTREMAL_WELD2_RATIO])
            result_data[EXTREMAL_WELD2_RATIO] = weld2_res_data

        ratio_data[EXTREMAL_SHEAR_RATIO] = max(ratios_list[EXTREMAL_SHEAR_RATIO])
        result_data[EXTREMAL_SHEAR_RATIO] = shear_res_data

        ratio_data[EXTREMAL_TENSION_RATIO] = max(ratios_list[EXTREMAL_TENSION_RATIO])
        result_data[EXTREMAL_TENSION_RATIO] = tension_res_data

        ratio_data[EXTREMAL_BENDING_RATIO] = max(ratios_list[EXTREMAL_BENDING_RATIO])
        result_data[EXTREMAL_BENDING_RATIO] = bending_res_data

        ratio_data[EXTREMAL_BENDING_TENSION_RATIO] = max(ratios_list[EXTREMAL_BENDING_TENSION_RATIO])
        result_data[EXTREMAL_BENDING_TENSION_RATIO] = bending_tension_res_data

        if self.connection_type == CONNECTION_BEAM_TO_COLUMN:
            ratio_data[EXTREMAL_COLUMN_SHEAR_RATIO] = max(ratios_list[EXTREMAL_COLUMN_SHEAR_RATIO])
            result_data[EXTREMAL_COLUMN_SHEAR_RATIO] = column_shear_res_data

        # this will save your results and set ratios in dlg
        r_obj.setResults(result_data)
        r_obj.setSummary(
            [[h, ratio_data[h]] for h in self.summarySubjects if h in result_data]
        )


        #
        #
        # # add message about ratio
        # if self.getResults().getUseRatio() > 1.:
        #     self.getMessageManager().addMessage(trans(u'!!!Nośność elementu przekroczona!!!.'),
        #                                         type=dnComponent.MSG_TYPE_ERROR)
        # else:
        #     self.getMessageManager().addMessage(trans(u'Element zaprojektowany poprawnie.'),
        #                                         type=dnComponent.MSG_TYPE_IMPORTANT)

        return True

    # def calc_plate_height(self):
    #     h = prof['h'] + self.dis_m1 + self.dis_m2 + e1 + e2
    #     if self.bolts_above:
    #         h += self.dis_e1
    #     if self.bolts_under:
    #         h += e2
    #     return h


    def insertRTFReport(self, docObj, sectionObj):
        # here you create rtf report
        pass

    def getDlgClass(self):
        import dnRigidBeamLib

        if self.getApp().isMsgMode():
            reload(dnRigidBeamLib)

        return RigidBeamConnectionDlg

    # other functions you need
    @property
    # def check_node(self):
    #     if self.selected_beam.getNodes()[0] == self.considered_node:
    #         self.binded_node = 0.
    #     else:
    #         self.binded_node = 1.
    #     return self.binded_node

    def _insertDesignCondHeading(self, rtf_report_methods,
                                 subject, results, title=True, title_prefix='', detail_data=True, suffix=''):

        ratio = results['ratio']
        ratio_exceeded = ratio > 1.0
        comb_data = results['comb_data']
        comb_name = results['comb_name']

        if title:
            rtf_report_methods.insertSubTitle(
                title_prefix + subject.encode('cp1250') + ' (%.1f ' % (float(ratio) * 100.) + '%)' + \
                ['', trans(' - Warunek przekroczony!!!')][ratio_exceeded],
                highlighted=ratio_exceeded)

        if detail_data:
            lg_data_str = ''
            lg_data = results['load_groups']
            if lg_data is not None and len(lg_data):
                lg_data_str = ' (%s)' % ''.join(['%s,' % lg for lg in lg_data])

            r_data = ''
            section_forces = comb_data['section_forces']

            for n, unit in [
                ['Ned', 'kN'],
                ['Ved', 'kN'],
                ['Med', 'kNm'],
            ]:
                r_data += '%s=%.1f%s, ' % (n, section_forces[n], unit)
            r_data = r_data[:-2]
            comb_name.encode('cp1250'),
            rtf_report_methods.insertText(trans('Komb: %s %s %s %s%s') %
                                          (comb_name, lg_data_str, r'\u8594\'3f', r_data, suffix),
                                          spaceAfter=150, fontEffect='italic')
