from enlib import enmap, lensing, powspec, utils
from szar.counts import ClusterCosmology
from alhazen.halos import NFWkappa
from orphics.analysis import flatMaps as fmaps
from alhazen.quadraticEstimator import Estimator
import alhazen.lensTools as lt
import orphics.tools.io as io
import orphics.tools.cmb as cmb
import orphics.tools.stats as stats
import os, sys
import numpy as np

# === PARAMS ===

Nsims = 100
sim_pixel_scale = 1.0 #0.1
analysis_pixel_scale = 1.0 #0.5
patch_width_arcmin = 55.*60. #100.
periodic = True
beam_arcmin = 1.0
noise_T_uK_arcmin = 0.1
noise_P_uK_arcmin = 0.1
lmax = 8000
tellmax = 8000
pellmax = 8000
tellmin = 200
pellmin = 200
kellmax = 8500
kellmin = 200
gradCut = 2000
pol = True
debug = True
cluster = False

out_dir = os.environ['WWW']+"plots/halotest/"


# === COSMOLOGY ===
cc = ClusterCosmology(lmax=lmax,pickling=True)
TCMB = 2.7255e6
theory = cc.theory


# === TEMPLATE MAPS ===

fine_ells = np.arange(0,lmax,1)
bin_edges = np.arange(0.,10.0,0.2)

shape_sim, wcs_sim = enmap.get_enmap_patch(patch_width_arcmin,sim_pixel_scale,proj="car",pol=pol)
modr_sim = enmap.modrmap(shape_sim,wcs_sim) * 180.*60./np.pi
binner_sim = stats.bin2D(modr_sim,bin_edges)

shape_dat, wcs_dat = enmap.get_enmap_patch(patch_width_arcmin,analysis_pixel_scale,proj="car",pol=pol)
modr_dat = enmap.modrmap(shape_dat,wcs_dat) * 180.*60./np.pi
binner_dat = stats.bin2D(modr_dat,bin_edges)




# === LENS ===

lxmap_sim,lymap_sim,modlmap_sim,angmap_sim,lx_dat,ly_dat = fmaps.get_ft_attributes_enmap(shape_sim,wcs_sim)
modl_map_alt = enmap.modlmap(shape_sim,wcs_sim)
assert np.all(np.isclose(modlmap_sim,modl_map_alt))


if cluster:
    massOverh = 2.e14
    zL = 0.7
    overdensity = 180.
    critical = False
    atClusterZ = False
    concentration = 3.2
    comS = cc.results.comoving_radial_distance(cc.cmbZ)*cc.h
    comL = cc.results.comoving_radial_distance(zL)*cc.h
    winAtLens = (comS-comL)/comS
    kappa_map,r500 = NFWkappa(cc,massOverh,concentration,zL,modr_sim,winAtLens,
                              overdensity=overdensity,critical=critical,atClusterZ=atClusterZ)
    #cents, nkprofile = binner.bin(kappa_map)
else:
    clkk = theory.gCl("kk",fine_ells)
    clkk.resize((1,1,clkk.size))
    kappa_map = enmap.rand_map(shape_sim[-2:],wcs_sim,cov=clkk,scalar=True)
    if debug:
        pkk = fmaps.get_simple_power_enmap(kappa_map)
        debug_edges = np.arange(kellmin,kellmax,80)
        dbinner = stats.bin2D(modlmap_sim,debug_edges)
        cents, bclkk = dbinner.bin(pkk)
        clkk.resize((clkk.shape[-1]))
        pl = io.Plotter(scaleY='log',scaleX='log')
        pl.add(fine_ells,clkk)
        pl.add(cents,bclkk)
        pl.done(out_dir+"clkk.png")
phi, fphi = lt.kappa_to_phi(kappa_map,modlmap_sim,return_fphi=True)
io.highResPlot2d(kappa_map,out_dir+"kappa_map.png")
io.highResPlot2d(phi,out_dir+"phi.png")
alpha_pix = enmap.grad_pixf(fphi)




# === EXPERIMENT ===


ntfunc = cmb.get_noise_func(beam_arcmin,noise_T_uK_arcmin,ellmin=tellmin,ellmax=tellmax,TCMB=2.7255e6)
npfunc = cmb.get_noise_func(beam_arcmin,noise_P_uK_arcmin,ellmin=pellmin,ellmax=pellmax,TCMB=2.7255e6)

nT_sim = ntfunc(modlmap_sim)
nP_sim = npfunc(modlmap_sim)






# === ESTIMATOR ===

template_dat = fmaps.simple_flipper_template_from_enmap(shape_dat,wcs_dat)
lxmap_dat,lymap_dat,modlmap_dat,angmap_dat,lx_dat,ly_dat = fmaps.get_ft_attributes_enmap(shape_dat,wcs_dat)
modl_map_alt = enmap.modlmap(shape_dat,wcs_dat)
assert np.all(np.isclose(modlmap_dat,modl_map_alt))

nT = ntfunc(modlmap_dat)
nP = npfunc(modlmap_dat)


fMaskCMB_T = fmaps.fourierMask(lx_dat,ly_dat,modlmap_dat,lmin=tellmin,lmax=tellmax)
fMaskCMB_P = fmaps.fourierMask(lx_dat,ly_dat,modlmap_dat,lmin=pellmin,lmax=pellmax)
fMask = fmaps.fourierMask(lx_dat,ly_dat,modlmap_dat,lmin=kellmin,lmax=kellmax)
qest = Estimator(template_dat,
                 theory,
                 theorySpectraForNorm=None,
                 noiseX2dTEB=[nT,nP,nP],
                 noiseY2dTEB=[nT,nP,nP],
                 fmaskX2dTEB=[fMaskCMB_T,fMaskCMB_P,fMaskCMB_P],
                 fmaskY2dTEB=[fMaskCMB_T,fMaskCMB_P,fMaskCMB_P],
                 fmaskKappa=fMask,
                 doCurl=False,
                 TOnly=not(pol),
                 halo=True,
                 gradCut=gradCut,verbose=True,
                 loadPickledNormAndFilters=None,
                 savePickledNormAndFilters=None)





# === ENMAP POWER ===

cltt = theory.uCl('TT',fine_ells)
clee = theory.uCl('EE',fine_ells)
clte = theory.uCl('TE',fine_ells)
clbb = theory.uCl('BB',fine_ells)
lcltt = theory.lCl('TT',fine_ells)
lclee = theory.lCl('EE',fine_ells)
lclte = theory.lCl('TE',fine_ells)
lclbb = theory.lCl('BB',fine_ells)
ps = np.zeros((3,3,fine_ells.size))
ps[0,0] = cltt
ps[1,1] = clee
ps[0,1] = clte
ps[1,0] = clte
ps[2,2] = clbb

# === SIM AND RECON LOOP ===

for i in range(Nsims):
    print i

    unlensed = enmap.rand_map(shape_sim,wcs_sim,ps)
    lensed = lensing.lens_map_flat_pix(unlensed, alpha_pix,order=5)
    if i==0 and debug:
        teb = enmap.ifft(enmap.map2harm(unlensed)).real
        lteb = enmap.ifft(enmap.map2harm(lensed)).real
        if pol:
            io.highResPlot2d(unlensed[0],out_dir+"tmap.png")
            io.highResPlot2d(unlensed[1],out_dir+"qmap.png")
            io.highResPlot2d(unlensed[2],out_dir+"umap.png")
            io.highResPlot2d(teb[1],out_dir+"emap.png")
            io.highResPlot2d(teb[2],out_dir+"bmap.png")
            io.highResPlot2d(lensed[0],out_dir+"ltmap.png")
            io.highResPlot2d(lensed[1],out_dir+"lqmap.png")
            io.highResPlot2d(lensed[2],out_dir+"lumap.png")
            io.highResPlot2d(lteb[1],out_dir+"lemap.png")
            io.highResPlot2d(lteb[2],out_dir+"lbmap.png")
        else:        
            io.highResPlot2d(unlensed,out_dir+"tmap.png")
            io.highResPlot2d(lensed,out_dir+"ltmap.png")

        
        t = teb[0,:,:]
        e = teb[1,:,:]
        b = teb[2,:,:]
        utt2d = fmaps.get_simple_power_enmap(t)
        uee2d = fmaps.get_simple_power_enmap(e)
        ute2d = fmaps.get_simple_power_enmap(enmap1=t,enmap2=e)
        ubb2d = fmaps.get_simple_power_enmap(b)
        debug_edges = np.arange(tellmin,tellmax,80)
        dbinner = stats.bin2D(modlmap_sim,debug_edges)
        cents, utt = dbinner.bin(utt2d)
        cents, uee = dbinner.bin(uee2d)
        cents, ute = dbinner.bin(ute2d)
        #cents, ubb = dbinner.bin(ubb2d)


        tl = lteb[0,:,:]
        el = lteb[1,:,:]
        bl = lteb[2,:,:]
        ltt2d = fmaps.get_simple_power_enmap(tl)
        lee2d = fmaps.get_simple_power_enmap(el)
        lte2d = fmaps.get_simple_power_enmap(enmap1=tl,enmap2=el)
        lbb2d = fmaps.get_simple_power_enmap(bl)
        cents, ltt = dbinner.bin(ltt2d)
        cents, lee = dbinner.bin(lee2d)
        cents, lte = dbinner.bin(lte2d)
        cents, lbb = dbinner.bin(lbb2d)

        
        pl = io.Plotter(scaleY='log',scaleX='log')
        pl.add(cents,utt*cents**2.,color="C0",ls="-")
        pl.add(cents,uee*cents**2.,color="C1",ls="-")
        #pl.add(cents,ubb*cents**2.,color="C2",ls="-")
        pl.add(fine_ells,cltt*fine_ells**2.,color="C0",ls="--")
        pl.add(fine_ells,clee*fine_ells**2.,color="C1",ls="--")
        #pl.add(fine_ells,clbb*fine_ells**2.,color="C2",ls="--")
        pl.done(out_dir+"ccomp.png")

        pl = io.Plotter(scaleX='log')
        pl.add(cents,ute*cents**2.,color="C0",ls="-")
        pl.add(fine_ells,clte*fine_ells**2.,color="C0",ls="--")
        pl.done(out_dir+"ccompte.png")

        pl = io.Plotter(scaleY='log',scaleX='log')
        pl.add(cents,ltt*cents**2.,color="C0",ls="-")
        pl.add(cents,lee*cents**2.,color="C1",ls="-")
        pl.add(cents,lbb*cents**2.,color="C2",ls="-")
        pl.add(fine_ells,lcltt*fine_ells**2.,color="C0",ls="--")
        pl.add(fine_ells,lclee*fine_ells**2.,color="C1",ls="--")
        pl.add(fine_ells,lclbb*fine_ells**2.,color="C2",ls="--")
        pl.done(out_dir+"lccomp.png")

        pl = io.Plotter(scaleX='log')
        pl.add(cents,lte*cents**2.,color="C0",ls="-")
        pl.add(fine_ells,lclte*fine_ells**2.,color="C0",ls="--")
        pl.done(out_dir+"lccompte.png")

        
