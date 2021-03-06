from Qt import QtGui, QtCore
import logging
import numpy
import fit
import patterson
logger = logging.getLogger("Viewer")

class AbstractParameterItem():
    def __init__(self,parentGroup,fileLoader,name,individualParamsDef,generalParamsDef):
        self.parentGroup = parentGroup
        self.fileLoader = fileLoader
        self.name = name
        self.path = parentGroup.fullName+"/"
        self.fullName = self.path+name
        self.paramsIndDef = individualParamsDef
        self.paramsGenDef = generalParamsDef
        self.paramsDirty = False
        self.dataItemImage = None
        self.dataItemMask = None
        self.indParams = {}
        self.genParams = {}
        self.dataItems = {}
        self.chunkSize = 10000
        self.numEvents = None
        self.initParams()
    def initParams(self):
        # return if we do not even know the stack size
        if self.fileLoader.stackSize is None:
            self.numEvents = self.chunkSize
        else:
            self.numEvents = self.fileLoader.stackSize - self.fileLoader.stackSize % self.chunkSize + self.chunkSize
        # set all general params to default values
        for n,v in self.paramsGenDef.items():
            self.genParams[n] = v
        #  set all individual params to default values
        for n,v in self.paramsIndDef.items():
            self.indParams[n] = numpy.ones(self.numEvents)*v
        # link to existing data items if there are any
        if self.name in self.parentGroup.children:
            gi = self.parentGroup.children[self.name]
            for n in self.paramsIndDef:
                if n in gi.children.keys():
                    self.dataItems[n] = gi.children[n]
            for n in self.paramsGenDef:
                if n in gi.children.keys():
                    self.dataItems[n] = gi.children[n]
        # read data from file if data items available
        for n,d in self.dataItems.items():
            data = d.data()
            if n in self.genParams:
                self.genParams[n] = data[0]
            elif n in self.indParams:
                while len(self.indParams[n]) < len(data):
                    v = self.paramsIndDef[n]
                    self.indParams[n] = numpy.append(self.indParams[n],numpy.ones(self.chunkSize)*v)
                self.indParams[n][:len(data)] = data[:]
    def getParams(self,img0):
        if (self.genParams == {}) or (self.indParams == {}):
           self.initParams()
        if img0 is None:
            img = 0
        else:
            img = img0
        # dynamically growing arrays for the case of SWMR operation
        while img >= self.numEvents:
            for n,v in self.paramsIndDef.items():
                self.indParams[n] = numpy.append(self.indParams[n],numpy.ones(self.chunkSize)*v)
            self.numEvents += self.chunkSize
        ps = {}
        for n,p in self.genParams.items():
            ps[n] = p
        for n,p in self.indParams.items():
            ps[n] = p[img]
        return ps
    def setParams(self,img,paramsNew):
        paramsOld = self.getParams(img)
        for n,pNew in paramsNew.items():
            if n in self.indParams:
                if pNew != paramsOld[n]:
                    self.paramsDirty = True
                    self.indParams[n][img] = pNew
            elif n in self.genParams:
                if pNew != paramsOld[n]:
                    self.paramsDirty = True
                    self.genParams[n] = pNew
    def saveParams(self):
        treeDirty = False
        if self.paramsDirty:
            if self.name in self.fileLoader[self.path].keys():
                grp = self.fileLoader[self.fullName]
            else:
                grp = self.fileLoader[self.path].create_group(self.name)
                self.fileLoader.reopenFile()
                self.fileLoader.addGroupPosterior(self.fullName)
                treeDirty = True
            for n,p0 in self.indParams.items():
                p = p0[:self.numEvents]
                grp = self.fileLoader[self.fullName]
                if n in grp:
                    ds = grp[n]
                    if ds.shape[0] != p.shape:
                        try:
                            ds.resize(p.shape)
                            ds[:self.numEvents] = p[:]
                        # FM: Fix to allow saving parameters on older files without chunked parameter datasets
                        except TypeError:
                            ds[:] = p[:ds.shape[0]]                            
                else:
                    ds = self.fileLoader[self.fullName].create_dataset(n,p.shape,maxshape=(None,),chunks=(10000,),data=self.indParams[n])
                    ds.attrs.modify("axes",["experiment_identifier"])
                    ds.attrs.modify("numEvents",[self.numEvents])
                    self.fileLoader.reopenFile()
                    self.fileLoader.addDatasetPosterior(self.fullName+"/"+n)
                    treeDirty = True
            for n,p in self.genParams.items():
                grp = self.fileLoader[self.fullName]
                if n in grp:
                    ds = grp[n]
                    ds[0] = p
                else:
                    ds = self.fileLoader[self.fullName].create_dataset(n,(1,),data=p)
                    self.fileLoader.reopenFile()
                    self.fileLoader.addDatasetPosterior(self.fullName+"/"+n)
                    treeDirty = True
            self.paramsDirty = False
        # the following two lines lead to a crash and a corrupt file, I have no clue why
        if treeDirty:
            self.fileLoader.fileLoaderExtended.emit()

class ModelItem(AbstractParameterItem):
    def __init__(self,parentGroup,fileLoader):
        self.settings = QtCore.QSettings()
        individualParamsDef = {"offCenterX": float(self.settings.value("modelCenterX")),
                               "offCenterY": float(self.settings.value("modelCenterY")),
                               "intensityMJUM2": float(self.settings.value("modelIntensity")),
                               "diameterNM": float(self.settings.value("modelDiameter")),
                               "fitError": numpy.nan,
                               "fitErrorOffCenterX": numpy.nan,
                               "fitErrorOffCenterY": numpy.nan,
                               "fitErrorIntensityMJUM2": numpy.nan,
                               "fitErrorDiameterNM": numpy.nan,
                               "maskRadius": float(self.settings.value("modelMaskRadius"))}
        generalParamsDef = {"photonWavelengthNM":1.,
                            "detectorDistanceMM":1000.,
                            "detectorPixelSizeUM":75.,
                            "detectorQuantumEfficiency":1.,
                            "detectorADUPhoton":10.,
                            "materialType":"water",
                            "_visibility":0.5,
                            "_modelMinimaAlpha":0.5,
                            "_maximumShift":5,
                            "_blurRadius":4,
                            "_nrEval":20,
                            "_doPhotonCounting":1,
                            "_findCenterMethod":'blurred', 
                            "_fitDiameterMethod":'pearson', 
                            "_fitIntensityMethod":'pixelwise', 
                            "_fitModelMethod":'fast'} 
        name = "model"
        AbstractParameterItem.__init__(self,parentGroup,fileLoader,name,individualParamsDef,generalParamsDef)
    def find_center(self,img):
        if img is None:
            QtGui.QMessageBox.warning(self.fileLoader.parent, self.fileLoader.parent.tr("CXI Viewer"),
                                      self.fileLoader.parent.tr("No image selected. Please click on the image that you want to use for center finding and try again."))
            return
        M = fit.FitModel(self.dataItemImage,self.dataItemMask)
        newParams = M.find_center(img,self.getParams(img))
        self.setParams(img,newParams)
    def fit_diameter(self, img):
        if img is None:
            QtGui.QMessageBox.warning(self.fileLoader.parent, self.fileLoader.parent.tr("CXI Viewer"),
                                      self.fileLoader.parent.tr("No image selected. Please click on the image that you want to use as input to fit the diameter and try again."))
            return
        M = fit.FitModel(self.dataItemImage,self.dataItemMask)
        newParams = M.fit_diameter(img,self.getParams(img))
        self.setParams(img,newParams)
    def fit_intensity(self, img):
        if img is None:
            QtGui.QMessageBox.warning(self.fileLoader.parent, self.fileLoader.parent.tr("CXI Viewer"),
                                      self.fileLoader.parent.tr("No image selected. Please click on the image that you want to use as input to fit the intensity and try again."))
            return
        M = fit.FitModel(self.dataItemImage,self.dataItemMask)
        newParams = M.fit_intensity(img,self.getParams(img))
        self.setParams(img,newParams)
    def fit_model(self,img):
        if img is None:
            QtGui.QMessageBox.warning(self.fileLoader.parent, self.fileLoader.parent.tr("CXI Viewer"),
                                      self.fileLoader.parent.tr("No image selected. Please click on the image that you want to use as input to fit the model and try again."))
            return
        M = fit.FitModel(self.dataItemImage,self.dataItemMask)
        newParams = M.fit_model(img,self.getParams(img))
        self.setParams(img,newParams)


class PattersonItem(AbstractParameterItem):
    def __init__(self,parentGroup,fileLoader):
        individualParamsDef = {"imageThreshold":30.,"maskSmooth":5.,"maskThreshold":0.2,"darkfield":False,"darkfieldX":0,"darkfieldY":0,"darkfieldSigma":100}
        generalParamsDef = {"_pattersonImg":-1}
        name = "patterson"
        AbstractParameterItem.__init__(self,parentGroup,fileLoader,name,individualParamsDef,generalParamsDef)
        self.textureLoaded = False
    def requestPatterson(self,img):
        self.textureLoaded = False
        self.setParams(img,{"_pattersonImg":img})

