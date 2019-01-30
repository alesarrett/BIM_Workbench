#***************************************************************************
#*                                                                         *
#*   Copyright (c) 2017 Yorik van Havre <yorik@uncreated.net>              *
#*                                                                         *
#*   This program is free software; you can redistribute it and/or modify  *
#*   it under the terms of the GNU Lesser General Public License (LGPL)    *
#*   as published by the Free Software Foundation; either version 2 of     *
#*   the License, or (at your option) any later version.                   *
#*   for detail see the LICENCE text file.                                 *
#*                                                                         *
#*   This program is distributed in the hope that it will be useful,       *
#*   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
#*   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
#*   GNU Library General Public License for more details.                  *
#*                                                                         *
#*   You should have received a copy of the GNU Library General Public     *
#*   License along with this program; if not, write to the Free Software   *
#*   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
#*   USA                                                                   *
#*                                                                         *
#***************************************************************************

"""This module contains FreeCAD commands for the BIM workbench"""

import os,FreeCAD,FreeCADGui,Draft,Arch,Part,csv,re
from PySide import QtCore,QtGui

def QT_TRANSLATE_NOOP(ctx,txt): return txt # dummy function for the QT translator

tests = ["testAll",
         "testIFC4",
         "testHierarchy",
         "testSites",
         "testBuildings",
         "testStoreys",
         "testUndefined",
         "testSolid",
         "testQuantities",
         "testCommonPsets",
         "testPsets",
         "testMaterials",
         "testStandards",
         "testExtrusions",
         "testStandardCases",
         "testTinyLines",
         "testRectangleProfileDef",
        ]

class BIM_Preflight:


    def GetResources(self):

        return {'Pixmap'  : os.path.join(os.path.dirname(__file__),"icons","BIM_Preflight.svg"),
                'MenuText': QT_TRANSLATE_NOOP("BIM_Preflight", "Preflight checks..."),
                'ToolTip' : QT_TRANSLATE_NOOP("BIM_Preflight", "Checks several characteristics of this model before exporting to IFC")}

    def Activated(self):
        FreeCADGui.Control.showDialog(BIM_Preflight_TaskPanel())



class BIM_Preflight_TaskPanel:


    def __init__(self):

        self.results = {} # to store the result message
        self.culprits = {} # to store objects to highlight
        self.rform = None # to store the results dialog
        self.form = FreeCADGui.PySideUic.loadUi(os.path.join(os.path.dirname(__file__),"dialogPreflight.ui"))
        self.form.setWindowIcon(QtGui.QIcon(os.path.join(os.path.dirname(__file__),"icons","BIM_Preflight.svg")))
        for test in tests:
            getattr(self.form,test).setIcon(QtGui.QIcon(":/icons/button_right.svg"))
            getattr(self.form,test).setToolTip("Press to perform the test")
            if hasattr(self,test):
                getattr(self.form,test).clicked.connect(getattr(self,test))
            self.results[test] = None
            self.culprits[test] = None


    def getStandardButtons(self):

        return int(QtGui.QDialogButtonBox.Close)


    def reject(self):

        QtGui.QApplication.restoreOverrideCursor()
        FreeCADGui.Control.closeDialog()
        FreeCAD.ActiveDocument.recompute()


    def passed(self,test):

        "sets the button as passed"

        getattr(self.form,test).setIcon(QtGui.QIcon(":/icons/button_valid.svg"))
        getattr(self.form,test).setText("Passed")
        getattr(self.form,test).setToolTip("This test has succeeded.")


    def failed(self,test):

        "sets the button as failed"

        getattr(self.form,test).setIcon(QtGui.QIcon(":/icons/process-stop.svg"))
        getattr(self.form,test).setText("Failed")
        getattr(self.form,test).setToolTip("This test has failed. Press the button to know more")


    def reset(self,test):

        "reset the button"

        getattr(self.form,test).setIcon(QtGui.QIcon(":/icons/button_right.svg"))
        getattr(self.form,test).setText("Test")
        getattr(self.form,test).setToolTip("Press to perform the test")


    def show(self,test):

        "shows test results"

        if self.results[test]:
            if self.culprits[test]:
                FreeCADGui.Selection.clearSelection()
                for c in self.culprits[test]:
                    FreeCADGui.Selection.addSelection(c)
            if not self.rform:
                self.rform = FreeCADGui.PySideUic.loadUi(os.path.join(os.path.dirname(__file__),"dialogPreflightResults.ui"))
                # center the dialog over FreeCAD window
                mw = FreeCADGui.getMainWindow()
                self.rform.move(mw.frameGeometry().topLeft() + mw.rect().center() - self.rform.rect().center())
                self.rform.buttonReport.clicked.connect(self.toReport)
                self.rform.buttonOK.clicked.connect(self.closeReport)
            self.rform.textBrowser.setText(self.results[test])
            label = test.replace("test","label")
            self.rform.label.setText(getattr(self.form,label).text())
            self.rform.test = test
            self.rform.show()


    def toReport(self):

        "copies the resulting text to the report view"

        if self.rform and hasattr(self.rform,"test") and self.rform.test:
            if self.results[self.rform.test]:
                FreeCAD.Console.PrintMessage(self.results[self.rform.test]+"\n")


    def closeReport(self):

        if self.rform:
            self.rform.test = None
            self.rform.hide()


    def getObjects(self):

        "selects target objects"

        objs = []
        if self.form.getAll.isChecked():
            objs = FreeCAD.ActiveDocument.Objects
        elif self.form.getVisible.isChecked():
            objs = [o for o in FreeCAD.ActiveDocument.Objects if o.ViewObject.Visibility == True]
        else:
            objs = FreeCADGui.Selection.getSelection()
        # clean objects list of unwanted types
        objs = Draft.getGroupContents(objs,walls=True,addgroups=True)
        objs = [obj for obj in objs if not obj.isDerivedFrom("Part::Part2DObject")]
        objs = [obj for obj in objs if not obj.isDerivedFrom("App::Annotation")]
        objs = [obj for obj in objs if (hasattr(obj,"Shape") and obj.Shape and not (obj.Shape.Edges and (not obj.Shape.Faces)))]
        objs = Arch.pruneIncluded(objs)
        objs = [obj for obj in objs if not obj.isDerivedFrom("App::DocumentObjectGroup")]
        objs = [obj for obj in objs if Draft.getType(obj) not in ["DraftText","Material","MaterialContainer","WorkingPlaneProxy"]]
        return objs


    def getToolTip(self,test):

        "gets the toolTip text from the ui file"

        label = test.replace("test","label")
        tooltip = getattr(self.form,label).toolTip()
        tooltip = tooltip.replace("</p>","</p>\n\n")
        tooltip = re.sub("<.*?>","",tooltip) # strip html tags
        return tooltip


    def testAll(self):

        "runs all tests"

        from DraftGui import todo
        for test in tests:
            if test != "testAll":
                QtGui.QApplication.processEvents()
                self.reset(test)
                if hasattr(self,test):
                    todo.delay(getattr(self,test),None)


    def testIFC4(self):

        "tests for IFC4 support"

        test = "testIFC4"
        if getattr(self.form,test).text() == "Failed":
            self.show(test)
        else:
            self.reset(test)
            self.results[test] = None
            self.culprits[test] = None
            msg = None
            try:
                import ifcopenshell
            except:
                msg = "ifcopenshell is not installed on your system or not available to FreeCAD. "
                msg += "This library is responsible for IFC support in FreeCAD, and therefore IFC support is currently disabled. "
                msg += "Check https://www.freecadweb.org/wiki/Extra_python_modules#IfcOpenShell to obtain more information. "
                self.failed(test)
            else:
                if ifcopenshell.schema_identifier.startswith("IFC4"):
                    self.passed(test)
                else:
                    msg = self.getToolTip(test)
                    msg += "The version of ifcopenshell installed on your system will produce files with this schema version:\n\n"
                    msg += ifcopenshell.schema_identifier + "\n\n"
                    self.failed(test)
            self.results[test] = msg


    def testHierarchy(self):

        "tests for project hierarchy support"

        test = "testHierarchy"
        if getattr(self.form,test).text() == "Failed":
            self.show(test)
        else:
            QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            self.reset(test)
            self.results[test] = None
            self.culprits[test] = []
            msg = None
            sites = False
            buildings = False
            storeys = False
            for obj in self.getObjects():
                if (Draft.getType(obj) == "Site") or (hasattr(obj,"IfcRole") and (obj.IfcRole == "Site")):
                    sites = True
                elif (Draft.getType(obj) == "Building") or (hasattr(obj,"IfcRole") and (obj.IfcRole == "Building")):
                    buildings = True
                elif (hasattr(obj,"IfcRole") and (obj.IfcRole == "Building Storey")):
                    storeys = True
            if (not sites) or (not buildings)  or (not storeys):
                msg = self.getToolTip(test)
                msg += "The following types were not found in the project:\n"
                if not sites:
                    msg += "\nSite"
                if not buildings:
                    msg += "\nBuilding"
                if not storeys:
                    msg += "\nBuilding Storey"
            if msg:
                self.failed(test)
            else:
                self.passed(test)
            self.results[test] = msg
            QtGui.QApplication.restoreOverrideCursor()


    def testSites(self):

        "tests for Sites support"

        test = "testSites"
        if getattr(self.form,test).text() == "Failed":
            self.show(test)
        else:
            QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            self.reset(test)
            self.results[test] = None
            self.culprits[test] = []
            msg = None
            for obj in self.getObjects():
                if (Draft.getType(obj) == "Building") or (hasattr(obj,"IfcRole") and (obj.IfcRole == "Building")):
                    ok = False
                    for parent in obj.InList:
                        if (Draft.getType(parent) == "Site") or (hasattr(parent,"IfcRole") and (parent.IfcRole == "Site")):
                            if hasattr(parent,"Group") and parent.Group:
                                if obj in parent.Group:
                                    ok = True
                                    break
                    if not ok:
                        self.culprits[test].append(obj)
                        if not msg:
                            msg = self.getToolTip(test)
                            msg += "The following Building objects have been found to not be included in any Site. "
                            msg += "You can resolve the situation by creating a Site object, if none is present "
                            msg += "in your model, and drag and drop the Building objects into it in the tree view:\n\n"
                        msg += obj.Label +"\n"
            if msg:
                self.failed(test)
            else:
                self.passed(test)
            self.results[test] = msg
            QtGui.QApplication.restoreOverrideCursor()


    def testBuildings(self):

        "tests for Buildings support"

        test = "testBuildings"
        if getattr(self.form,test).text() == "Failed":
            self.show(test)
        else:
            QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            self.reset(test)
            self.results[test] = None
            self.culprits[test] = []
            msg = None
            for obj in self.getObjects():
                if hasattr(obj,"IfcRole") and (obj.IfcRole == "Building Storey"):
                    ok = False
                    for parent in obj.InList:
                        if hasattr(parent,"IfcRole") and (parent.IfcRole == "Building"):
                            if hasattr(parent,"Group") and parent.Group:
                                if obj in parent.Group:
                                    ok = True
                                    break
                    if not ok:
                        self.culprits[test].append(obj)
                        if not msg:
                            msg = self.getToolTip(test)
                            msg += "The following Building Storey (BuildingParts with their IFC role set as \"Building Storey\")"
                            msg += "objects have been found to not be included in any Building. "
                            msg += "You can resolve the situation by creating a Building object, if none is present "
                            msg += "in your model, and drag and drop the Building Storey objects into it in the tree view:\n\n"
                        msg += obj.Label +"\n"
            if msg:
                self.failed(test)
            else:
                self.passed(test)
            self.results[test] = msg
            QtGui.QApplication.restoreOverrideCursor()


    def testStoreys(self):

        "tests for Building Storey support"

        test = "testStoreys"
        if getattr(self.form,test).text() == "Failed":
            self.show(test)
        else:
            QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            self.reset(test)
            self.results[test] = None
            self.culprits[test] = []
            msg = None
            for obj in self.getObjects():
                if hasattr(obj,"IfcRole") and (not obj.IfcRole in ["Building","Building Storey","Site"]):
                    ok = False
                    for parent in obj.InListRecursive:
                        # just check if any of the ancestors is a Building Storey for now. Don't check any further...
                        if hasattr(parent,"IfcRole") and (parent.IfcRole == "Building Storey"):
                            ok = True
                            break
                    if not ok:
                        self.culprits[test].append(obj)
                        if not msg:
                            msg = self.getToolTip(test)
                            msg += "The following BIM objects have been found to not be included in any Building Storey "
                            msg += "(BuildingParts with their IFC role set as \"Building Storey\"). "
                            msg += "You can resolve the situation by creating a Building Storey object, if none is present "
                            msg += "in your model, and drag and drop these objects into it in the tree view:\n\n"
                        msg += obj.Label +"\n"
            if msg:
                self.failed(test)
            else:
                self.passed(test)
            self.results[test] = msg
            QtGui.QApplication.restoreOverrideCursor()


    def testUndefined(self):

        "tests for undefined BIM objects"

        test = "testUndefined"
        if getattr(self.form,test).text() == "Failed":
            self.show(test)
        else:
            QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            self.reset(test)
            self.results[test] = None
            self.culprits[test] = []
            undefined = []
            notbim = []
            msg = None

            for obj in self.getObjects():
                if hasattr(obj,"IfcRole"):
                    if (obj.IfcRole == "Undefined"):
                        self.culprits[test].append(obj)
                        undefined.append(obj)
                else:
                    self.culprits[test].append(obj)
                    notbim.append(obj)
            if undefined or notbim:
                msg = self.getToolTip(test)
                if undefined:
                    msg += "The following BIM objects have the \"Undefined\" type:\n\n"
                    for o in undefined:
                        msg += o.Label + "\n"
                if notbim:
                    msg += "The following objects are not BIM objects:\n\n"
                    for o in notbim:
                        msg += o.Label + "\n"
                        msg += "You can turn these objects into BIM objects by using the Utils -> Make Component tool."
            if msg:
                self.failed(test)
            else:
                self.passed(test)
            self.results[test] = msg
            QtGui.QApplication.restoreOverrideCursor()


    def testSolid(self):

        "tests for invalid/non-solid BIM objects"

        test = "testSolid"
        if getattr(self.form,test).text() == "Failed":
            self.show(test)
        else:
            QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            self.reset(test)
            self.results[test] = None
            self.culprits[test] = []
            msg = None

            for obj in self.getObjects():
                if obj.isDerivedFrom("Part::Feature"):
                    if (not obj.Shape.isNull()) and ((not obj.Shape.isValid()) or (not obj.Shape.Solids)):
                        self.culprits[test].append(obj)
            if self.culprits[test]:
                msg = self.getToolTip(test)
                msg += "The following BIM objects have an invalid or non-solid geometry:\n\n"
                for o in self.culprits[test]:
                    msg += o.Label + "\n"
            if msg:
                self.failed(test)
            else:
                self.passed(test)
            self.results[test] = msg
            QtGui.QApplication.restoreOverrideCursor()


    def testQuantities(self):

        "tests for explicit quantities export"

        test = "testQuantities"
        if getattr(self.form,test).text() == "Failed":
            self.show(test)
        else:
            QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            self.reset(test)
            self.results[test] = None
            self.culprits[test] = []
            msg = None

            for obj in self.getObjects():
                if hasattr(obj,"IfcAttributes") and (Draft.getType(obj) != "BuildingPart"):
                    for prop in ["Length","Width","Height"]:
                        if prop in obj.PropertiesList:
                            if (not "Export"+prop in obj.IfcAttributes) or (obj.IfcAttributes["Export"+prop] == "False"):
                                self.culprits[test].append(obj)
                                break
            if self.culprits[test]:
                msg = self.getToolTip(test)
                msg += "The objects below have Length, Width or Height properties, "
                msg += "but these properties won't be explicitely exported to IFC. "
                msg += "This is not necessarily an issue, unless you specifically want these "
                msg += "quantities to be exported:\n\n"
                for o in self.culprits[test]:
                    msg += o.Label + "\n"
                msg += "\nTo enable exporting of these quantities, use the IFC quantities manager tool "
                msg += "located under menu Manage -> Manage IFC Quantities..."
            if msg:
                self.failed(test)
            else:
                self.passed(test)
            self.results[test] = msg
            QtGui.QApplication.restoreOverrideCursor()


    def testCommonPsets(self):

        "tests for common property sets"

        test = "testCommonPsets"
        if getattr(self.form,test).text() == "Failed":
            self.show(test)
        else:
            QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            self.reset(test)
            self.results[test] = None
            self.culprits[test] = []
            msg = None
            psets = []
            psetspath = os.path.join(FreeCAD.getResourceDir(),"Mod","Arch","Presets","pset_definitions.csv")
            if os.path.exists(psetspath):
                with open(psetspath, "r") as csvfile:
                    reader = csv.reader(csvfile, delimiter=';')
                    for row in reader:
                        if "Common" in row[0]:
                            psets.append(row[0][5:-6])
            psets = [''.join(map(lambda x: x if x.islower() else " "+x, p)) for p in psets]
            psets = [pset.strip() for pset in psets]
            #print(psets)

            for obj in self.getObjects():
                ok = True
                if hasattr(obj,"IfcRole") and hasattr(obj,"IfcProperties") and isinstance(obj.IfcProperties,dict):
                    if obj.IfcRole in psets:
                        ok = False
                        if "Pset_"+obj.IfcRole.replace(" ","")+"Common" in ','.join(obj.IfcProperties.values()):
                            ok = True
                if not ok:
                    self.culprits[test].append(obj)

            if self.culprits[test]:
                msg = self.getToolTip(test)
                msg += "The objects below have a defined IFC type but do not have the associated common property set:\n\n"
                for o in self.culprits[test]:
                    msg += o.Label + "\n"
                msg += "\nTo add common property sets to these objects, use the IFC properties manager tool "
                msg += "located under menu Manage -> Manage IFC Properties..."
            if msg:
                self.failed(test)
            else:
                self.passed(test)
            self.results[test] = msg
            QtGui.QApplication.restoreOverrideCursor()


    def testPsets(self):

        "tests for property sets integrity"

        test = "testPsets"
        if getattr(self.form,test).text() == "Failed":
            self.show(test)
        else:
            QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            self.reset(test)
            self.results[test] = None
            self.culprits[test] = []
            msg = None
            psets = {}
            psetspath = os.path.join(FreeCAD.getResourceDir(),"Mod","Arch","Presets","pset_definitions.csv")
            if os.path.exists(psetspath):
                with open(psetspath, "r") as csvfile:
                    reader = csv.reader(csvfile, delimiter=';')
                    for row in reader:
                        if "Common" in row[0]:
                            psets[row[0]] = row[1:]
 
            for obj in self.getObjects():
                ok = True
                if hasattr(obj,"IfcRole") and hasattr(obj,"IfcProperties") and isinstance(obj.IfcProperties,dict):
                    if obj.IfcRole != "Undefined":
                        found = None
                        for pset in psets.keys():
                            for val in obj.IfcProperties.values():
                                if pset in val:
                                    found = pset
                                    break
                        if found:
                            for i in range(int(len(psets[found])/2)):
                                p = psets[found][i*2]
                                t = psets[found][i*2+1]
                                #print("testing for ",p,t,found," in ",obj.IfcProperties)
                                if p in obj.IfcProperties:
                                    if (not found in obj.IfcProperties[p]) or (not t in obj.IfcProperties[p]):
                                        ok = False
                                else:
                                    ok = False
                if not ok:
                    self.culprits[test].append(obj)

            if self.culprits[test]:
                msg = self.getToolTip(test)
                msg += "The objects below have a common property set but that property set doesn't contain all the needed properties:\n\n"
                for o in self.culprits[test]:
                    msg += o.Label + "\n"
                msg += "\nVerify which properties a certain property set must contain on http://www.buildingsmart-tech.org/ifc/IFC4/Add2/html/annex/annex-b/alphabeticalorder_psets.htm\n\n"
                msg += "To fix the property sets of these objects, use the IFC properties manager tool "
                msg += "located under menu Manage -> Manage IFC Properties..."
            if msg:
                self.failed(test)
            else:
                self.passed(test)
            self.results[test] = msg
            QtGui.QApplication.restoreOverrideCursor()


    def testMaterials(self):

        "tests for materials in BIM objects"

        test = "testMaterials"
        if getattr(self.form,test).text() == "Failed":
            self.show(test)
        else:
            QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            self.reset(test)
            self.results[test] = None
            self.culprits[test] = []
            msg = None
            for obj in self.getObjects():
                if "Material" in obj.PropertiesList:
                    if not obj.Material:
                        self.culprits[test].append(obj)
            if self.culprits[test]:
                msg = self.getToolTip(test)
                msg += "The following BIM objects have no material attributed:\n\n"
                for o in self.culprits[test]:
                    msg += o.Label + "\n"
            if msg:
                self.failed(test)
            else:
                self.passed(test)
            self.results[test] = msg
            QtGui.QApplication.restoreOverrideCursor()


    def testStandards(self):

        "tests for standards in BIM objects"

        test = "testStandards"
        if getattr(self.form,test).text() == "Failed":
            self.show(test)
        else:
            QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            self.reset(test)
            self.results[test] = None
            self.culprits[test] = []
            msg = None
            for obj in self.getObjects():
                if "StandardCode" in obj.PropertiesList:
                    if not obj.StandardCode:
                        self.culprits[test].append(obj)
                if "Material" in obj.PropertiesList:
                    if obj.Material:
                        if "StandardCode" in obj.Material.PropertiesList:
                            if not obj.Material.StandardCode:
                                self.culprits[test].append(obj.Material)
            if self.culprits[test]:
                msg = self.getToolTip(test)
                msg += "The following BIM objects have no defined standard code:\n\n"
                for o in self.culprits[test]:
                    msg += o.Label + "\n"
            if msg:
                self.failed(test)
            else:
                self.passed(test)
            self.results[test] = msg
            QtGui.QApplication.restoreOverrideCursor()


    def testExtrusions(self):

        "tests is all objects are extrusions"

        test = "testExtrusions"
        if getattr(self.form,test).text() == "Failed":
            self.show(test)
        else:
            QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            self.reset(test)
            self.results[test] = None
            self.culprits[test] = []
            msg = None
            for obj in self.getObjects():
                if hasattr(obj,"Proxy"):
                    if hasattr(obj,"IfcAttributes") and ("FlagForceBrep" in obj.IfcAttributes.keys()) and (obj.IfcAttributes["FlagForceBrep"] == "True"):
                        self.culprits[test].append(obj)
                    elif hasattr(obj.Proxy,"getExtrusionData") and not obj.Proxy.getExtrusionData(obj):
                        self.culprits[test].append(obj)
                    elif Draft.getType(obj) == "BuildingPart":
                        pass
                elif obj.isDerivedFrom("Part::Extrusion"):
                    pass
                elif obj.isDerivedFrom("App::DocumentObjectGroup"):
                    pass
                elif obj.isDerivedFrom("App::MaterialObject"):
                    pass
                else:
                    self.culprits[test].append(obj)
            if self.culprits[test]:
                msg = self.getToolTip(test)
                msg += "The following BIM objects are not extrusions:\n\n"
                for o in self.culprits[test]:
                    msg += o.Label + "\n"
            if msg:
                self.failed(test)
            else:
                self.passed(test)
            self.results[test] = msg
            QtGui.QApplication.restoreOverrideCursor()


    def testStandardCases(self):

        "tests for structs and wall standard cases"

        test = "testStandardCases"
        if getattr(self.form,test).text() == "Failed":
            self.show(test)
        else:
            QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            self.reset(test)
            self.results[test] = None
            self.culprits[test] = []
            msg = None
            for obj in self.getObjects():
                if Draft.getType(obj) == "Wall":
                    if obj.Base and (len(obj.Base.Shape.Edges) != 1):
                        self.culprits[test].append(obj)
                elif Draft.getType(obj) == "Structure":
                    if obj.Base and ( (len(obj.Base.Shape.Wires) != 1) or (not obj.Base.Shape.Wires[0].isClosed()) ):
                        self.culprits[test].append(obj)
            if self.culprits[test]:
                msg = self.getToolTip(test)
                msg += "The following BIM objects are not standard cases:\n\n"
                for o in self.culprits[test]:
                    msg += o.Label + "\n"
            if msg:
                self.failed(test)
            else:
                self.passed(test)
            self.results[test] = msg
            QtGui.QApplication.restoreOverrideCursor()


    def testTinyLines(self):

        "tests for objects with tiny lines (< 0.8mm)"

        test = "testTinyLines"
        if getattr(self.form,test).text() == "Failed":
            self.show(test)
        else:
            QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            self.reset(test)
            self.results[test] = None
            self.culprits[test] = []
            msg = None
            minl = 0.79376 # min 1/32"
            edges = []
            objs = []
            for obj in self.getObjects():
                if obj.isDerivedFrom("Part::Feature"):
                    if obj.Shape:
                        for e in obj.Shape.Edges:
                            if e.Length <= minl:
                                edges.append(e)
                                if not obj in objs:
                                    objs.append(obj)
            if edges:
                result = FreeCAD.ActiveDocument.addObject("Part::Feature","TinyLinesResult")
                result.Shape = Part.makeCompound(edges)
                result.ViewObject.LineWidth = 5
                self.culprits[test] = [result]
                msg = self.getToolTip(test)
                msg += "The objects below have lines smaller than 1/32 inch or 0.79 mm, which is the smallest "
                msg += "line size that Revit accepts. These objects will be discarded when imported into Revit:\n\n"
                for obj in objs:
                    msg += obj.Label +"\n"
                msg += "\nAn additional object, called \"TinyLinesResult\" has been added to this model, and "
                msg += "selected. It contains all the tiny lines found, so you can inspect them and fix the "
                msg += "needed objects. Be sure to delete the TinyLinesResult object when you are done!\n\n"
                msg += "Tip: The results are best viewed in Wireframe mode (menu Views -> Draw Style -> Wireframe)"
            if msg:
                self.failed(test)
            else:
                self.passed(test)
            self.results[test] = msg
            QtGui.QApplication.restoreOverrideCursor()


    def testRectangleProfileDef(self):

        "tests for RectangleProfileDef disable"

        test = "testRectangleProfileDef"
        if getattr(self.form,test).text() == "Failed":
            self.show(test)
        else:
            self.reset(test)
            self.results[test] = None
            self.culprits[test] = None
            msg = None
            if FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Arch").GetBool("DisableIfcRectangleProfileDef",False):
                self.passed(test)
            else:
                msg = self.getToolTip(test)
                self.failed(test)
            self.results[test] = msg



FreeCADGui.addCommand('BIM_Preflight',BIM_Preflight())
