#from PyQt4 import QtGui, QtCore, QtOpenGL, Qt
from PySide import QtGui, QtCore, QtOpenGL
import h5py
from operator import mul
import numpy
import sys,os
from cxi.groupitem import GroupItem
from cxi.cxi import CXI

class DataButton(QtGui.QPushButton):
    needData = QtCore.Signal(str)    
    def __init__(self,dataBox,imageFile,dataMode,menu=None):
        QtGui.QPushButton.__init__(self)
        self.dataBox = dataBox
        self.dataMode = dataMode
        self.setName()
        self.setIcon(QtGui.QIcon(imageFile))
        S = 30
        Htot = S + 15
        Wtot = 400
        self.setIconSize(QtCore.QSize(S,S))
        self.setToolTip("drag data here")
        self.setAcceptDrops(True)
        if menu != None:
            self.setMenu(menu)
    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat('text/plain'):
            e.accept()
        else:
            e.ignore() 
    def dropEvent(self, e):
        t = e.mimeData().text()
        self.needData.emit(t)
    def setName(self,name=None):
        if name == None:
            self.setStyleSheet("text-align: left; font-style: italic")
            self.setText("drag %s data here" % self.dataMode)
        else:
            self.setStyleSheet("text-align: left; font-style: roman") 
            self.setText(name)

class DataBox(QtGui.QHBoxLayout):
    def __init__(self,imageFile,dataMode,menu):
        QtGui.QHBoxLayout.__init__(self)
        self.menu = menu
        self.button = DataButton(self,imageFile,dataMode,menu)
        self.addWidget(self.button)
        self.vbox = QtGui.QVBoxLayout()
        self.addLayout(self.vbox)
        if menu != None:
            self.menu.clearAction.triggered.connect(self.clear)
    def clear(self):
        self.button.setName()
        self.button.needData.emit(None)

class DataMenu(QtGui.QMenu):
    def __init__(self,parent=None):
        QtGui.QMenu.__init__(self,parent)
        self.clearAction = self.addAction("Clear")

class DataMaskMenu(DataMenu):
    def __init__(self,parent=None):
        DataMenu.__init__(self,parent)
        self.addSeparator()
        self.PIXELMASK_BITS = {'perfect' : CXI.PIXEL_IS_PERFECT,
                               'invalid' : CXI.PIXEL_IS_INVALID,
                               'saturated' : CXI.PIXEL_IS_SATURATED,
                               'hot' : CXI.PIXEL_IS_HOT,
                               'dead' : CXI.PIXEL_IS_DEAD,
                               'shadowed' : CXI.PIXEL_IS_SHADOWED,
                               'peakmask' : CXI.PIXEL_IS_IN_PEAKMASK,
                               'ignore' : CXI.PIXEL_IS_TO_BE_IGNORED,
                               'bad' : CXI.PIXEL_IS_BAD,
                               'resolution' : CXI.PIXEL_IS_OUT_OF_RESOLUTION_LIMITS,
                               'missing' : CXI.PIXEL_IS_MISSING,
                               'halo' : CXI.PIXEL_IS_IN_HALO}
        self.maskActions = {}
        for key in self.PIXELMASK_BITS.keys():
            self.maskActions[key] = self.addAction(key)
            self.maskActions[key].setCheckable(True)
            self.maskActions[key].setChecked(True)
        self.maskActions["resolution"].setChecked(False)
    def getMaskOutBits(self):
        maskOutBits=0
        for key in self.maskActions:
            if self.maskActions[key].isChecked():
                maskOutBits |= self.PIXELMASK_BITS[key]
        return maskOutBits
        

class DataPlotMenu(DataMenu):
    def __init__(self,parent=None):
        DataMenu.__init__(self,parent)
        self.addSeparator()
        actionGroup = QtGui.QActionGroup(self)
        actionGroup.setExclusive(True)
        self.plotActions = {}
        keys = ["plot","average","histogram"]
        for key in keys:
            self.plotActions[key] = actionGroup.addAction(key)
            self.addAction(self.plotActions[key])
            self.plotActions[key].setCheckable(True)
        self.plotActions["plot"].setChecked(True)
    def getPlotMode(self):
        for key in self.plotActions.keys():
            if self.plotActions[key].isChecked():
                return key        


class CXINavigation(QtGui.QWidget):
    def __init__(self,parent=None):
        QtGui.QWidget.__init__(self,parent)
        self.parent = parent
        self.vbox = QtGui.QVBoxLayout()
        self.setLayout(self.vbox)

        self.dataMenus = {}
        self.dataBoxes = {}

        self.dataMenus["image"] = DataMenu(self)
        self.basePath = os.path.dirname(os.path.realpath(__file__))
        self.dataBoxes["image"] = DataBox(self.basePath + "/icons/image.png","image",self.dataMenus["image"])
        self.vbox.addLayout(self.dataBoxes["image"])

        self.dataMenus["mask"] = DataMaskMenu(self)
        self.dataBoxes["mask"] = DataBox(self.basePath + "/icons/mask_simple.png","mask",self.dataMenus["mask"])
        self.vbox.addLayout(self.dataBoxes["mask"])

        self.dataMenus["sort"] = DataMenu(self)
        self.dataBoxes["sort"] = DataBox(self.basePath + "/icons/sort.png","sort",self.dataMenus["sort"])
        self.vbox.addLayout(self.dataBoxes["sort"])

        self.dataBoxes["filter0"] = DataBox(self.basePath + "/icons/filter.png","filter",None)
        self.vbox.addLayout(self.dataBoxes["filter0"])

        self.vboxFilters = QtGui.QVBoxLayout()
        #self.vboxFilters.setDirection(QtGui.QBoxLayout.BottomToTop)
        self.vbox.addLayout(self.vboxFilters)
        self.dataMenus["filters"] = []
        self.dataBoxes["filters"] = []

        line = QtGui.QFrame()
        line.setFrameShape(QtGui.QFrame.HLine)
        self.vbox.addWidget(line)

        self.dataMenus["plot X"] = DataMenu(self)
        self.dataBoxes["plot X"] = DataBox(self.basePath + "/icons/plotX.png","plot X",self.dataMenus["plot X"])
        self.vbox.addLayout(self.dataBoxes["plot X"])

        self.dataMenus["plot Y"] = DataPlotMenu(self)
        self.dataBoxes["plot Y"] = DataBox(self.basePath + "/icons/plotY.png","plot Y",self.dataMenus["plot Y"])
        self.vbox.addLayout(self.dataBoxes["plot Y"])

        self.CXITree = CXITree(self)
        self.vbox.addWidget(self.CXITree)

    def addFilterBox(self):
        menu = DataMenu(self)
        self.dataMenus["filters"].append(menu)
        box = DataBox(self.basePath + "/icons/filter.png","filter",menu)
        self.dataBoxes["filters"].append(box)
        self.vboxFilters.addLayout(box)
        return box

    def removeFilterBox(self,filterBox):
        i = self.dataBoxes["filters"].index(filterBox)
        self.dataBoxes["filters"][i].removeWidget(self.dataBoxes["filters"][i].button)
        self.dataBoxes["filters"][i].button.setParent(None)
        self.dataBoxes["filters"].pop(i)
        self.dataMenus["filters"].pop(i)
        

class CXITree(QtGui.QTreeWidget):
    dataClicked = QtCore.Signal(str)    
    def __init__(self,parent=None):        
        QtGui.QTreeWidget.__init__(self,parent)
        self.parent = parent
        self.columnName = 0
        self.columnPath = 1
        self.itemExpanded.connect(self.treeChanged)
        self.itemCollapsed.connect(self.treeChanged)
        #self.setHeaderLabels(["CXI-file tree"])
        self.resizeColumnToContents(0)
        self.itemClicked.connect(self.handleClick)
        self.setDragEnabled(True)
        self.header().close()
    def treeChanged(self):
        self.manageSizes()
    def manageSizes(self):
        self.resizeColumnToContents(0)
    def buildTree(self,fileLoader):
        self.fileLoader = fileLoader
        self.clear();
        self.setColumnCount(1)
        self.root = QtGui.QTreeWidgetItem(["/"])
        self.addTopLevelItem(self.root)
        self.root.setExpanded(True)
        self.item = QtGui.QTreeWidgetItem([fileLoader.filename])
        self.item.setToolTip(0,fileLoader.fullFilename)
        self.root.addChild(self.item)
        self.updateTree()
    def updateTree(self):
        self.updateBranch(self.fileLoader,self.item)
    def updateBranch(self,group,branch):
        groupChildrenNames = group.children.keys()
        groupChildrenNames.sort()
        branchChildrenNames = [branch.child(i).text(self.columnName) for i in range(branch.childCount())]
        for i,k in enumerate(groupChildrenNames):
            child = group.children[k]
            item = QtGui.QTreeWidgetItem([k,child.fullName])
            if(isinstance(child,GroupItem)):
                if k not in branchChildrenNames:
                    item = QtGui.QTreeWidgetItem([k,child.fullName])
                else:
                    item = branch.child(branchChildrenNames.index(k))
                self.updateBranch(child,item)
                branch.insertChild(i,item)
            else:
                if k not in branchChildrenNames:
                    ds_dtype = child.dtypeName
                    ds_shape = child.shape()
                    # make tooltip
                    string = "<i>"+ds_dtype+"</i> ("
                    for d in ds_shape:
                        string += str(d)+","
                    string = string[:-1]
                    string += ")"
                    item.setToolTip(self.columnPath-1,string)
                    numDims = child.format
                    S = 50
                    # 0D blue
                    if numDims == 0:
                        R = 255-S
                        G = 255-S
                        B = 255
                        prop = "1D"
                    # 1D red
                    elif numDims == 1:
                        R = 255
                        G = 255-S
                        B = 255-S
                        prop = "3D"
                    # 2D green
                    elif numDims == 2:
                        R = 255-S
                        G = 255
                        B = 255-S 
                        prop = "2D"
                    # default grey
                    else:
                        R = 255-S
                        G = 255-S
                        B = 255-S
                        prop = "default"
                    # datsets which are not stacks lighter
                    isStack = child.isStack
                    if not isStack:
                        fade = S
                        R -= fade
                        G -= fade
                        B -= fade
                        prop += "Stack"
                    item.setForeground(0,QtGui.QBrush(QtGui.QColor(R,G,B)))
                    # make bold if it is a data called 'data'
                    if child.name == 'data':
                        font = QtGui.QFont()
                        font.setBold(True)
                        item.setFont(0,font)
                    branch.insertChild(i,item)
    def loadData(self,path=None):
        found,child = self.expandTree(path)
        if found:
            self.handleClick(child,1)
            return 1
        return 0
    def expandTree(self,path=None):
        root = self.item
        root.setExpanded(True)
        if path == None:
            path = "entry_1/image_1/data"
        for j,section in zip(range(len(path.split("/"))),path.split("/")):
            if section == "":
                continue
            found = False
            for i in range(0,root.childCount()):
                child = root.child(i)
                if(child.text(self.columnPath).split("/")[-1] == section):
                    child.setExpanded(True)
                    root = child
                    found = True
                    break
            if not found:
                break
        return found,child
    def startDrag(self, event):
        # create mime data object
        mime = QtCore.QMimeData()
        mime.setText(self.currentItem().text(self.columnPath))
        # start drag 
        drag = QtGui.QDrag(self)
        drag.setMimeData(mime)
        drag.start(QtCore.Qt.MoveAction)
    def handleClick(self,item,column):
        if(item.text(self.columnPath) in self.fileLoader.dataItems.keys()):
            self.dataClicked.emit(item.text(self.columnPath))

