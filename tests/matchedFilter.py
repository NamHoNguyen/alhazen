from orphics.tools.output import Plotter
import flipper.liteMap as lm
from szlib.szcounts import ClusterCosmology,dictFromSection,listFromConfig
from ConfigParser import SafeConfigParser 
from alhazen.halos import NFWMatchedFilterVar
import numpy as np
from orphics.tools.cmb import loadTheorySpectraFromCAMB
from alhazen.quadraticEstimator import NlGenerator,getMax

M = 2.e14
z = 0.7
c = 1.84

clusterParams = 'LACluster' # from ini file
cosmologyName = 'LACosmology' # from ini file

iniFile = "../SZ_filter/input/params.ini"
Config = SafeConfigParser()
Config.optionxform=str
Config.read(iniFile)

lmax = 8000

cosmoDict = dictFromSection(Config,cosmologyName)
constDict = dictFromSection(Config,'constants')
clusterDict = dictFromSection(Config,clusterParams)
cc = ClusterCosmology(cosmoDict,constDict,lmax)







# Make a CMB Noise Curve
cambRoot = "data/ell28k_highacc"
gradCut = 2000
halo = True
beamX = 1.0
beamY = 1.0
noiseTX = 1.0
noisePX = 1.414
noiseTY = 1.0
noisePY = 1.414
tellmin = 2
tellmax = 8000
gradCut = 2000
pellmin = 2
pellmax = 8000
polComb = 'EB'
kmin = 100
kmax = getMax(polComb,tellmax,pellmax)

deg = 10.
px = 0.5
dell = 10
bin_edges = np.arange(kmin,kmax,dell)+dell
theory = loadTheorySpectraFromCAMB(cambRoot,unlensedEqualsLensed=False,useTotal=False,lpad=9000)
lmap = lm.makeEmptyCEATemplate(raSizeDeg=deg, decSizeDeg=deg,pixScaleXarcmin=px,pixScaleYarcmin=px)
myNls = NlGenerator(lmap,theory,bin_edges,gradCut=gradCut)
myNls.updateNoise(beamX,noiseTX,noisePX,tellmin,tellmax,pellmin,pellmax,beamY=beamY,noiseTY=noiseTY,noisePY=noisePY)
ls,Nls = myNls.getNl(polComb=polComb,halo=halo)

ellkk = np.arange(2,9000,1)
Clkk = theory.gCl("kk",ellkk)    
pl = Plotter(scaleY='log',scaleX='log')
pl.add(ellkk,4.*Clkk/2./np.pi)
pl.add(ls,4.*Nls/2./np.pi)
pl.legendOn(loc='lower left',labsize=10)
pl.done("output/nl.png")




arcStamp = 20.
pxStamp = 0.01
lmap = lm.makeEmptyCEATemplate(raSizeDeg=arcStamp/60., decSizeDeg=arcStamp/60.,pixScaleXarcmin=pxStamp,pixScaleYarcmin=pxStamp)




NFWMatchedFilterVar(lmap,cc,M,c,z,ells=ls,Nls=Nls)


