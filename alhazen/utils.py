from __future__ import print_function
from enlib import enmap, lensing, powspec, bench
from enlib import utils as u
import sys
import numpy as np
from orphics.tools.mpi import mpi_distribute, MPIStats
import orphics.tools.io as io
from orphics.tools.stats import bin2D
import orphics.tools.cmb as cmb
from alhazen.quadraticEstimator import Estimator
import orphics.analysis.flatMaps as fmaps
import contextlib
@contextlib.contextmanager
def ignore():
    yield None
    
class RotTestPipeline(object):


    def __init__(self,full_sky_pix,wdeg,hdeg,yoffset,mpi_comm=None,nsims=1,lmax=7000,pix_intermediate=None):
        self.dtype = np.float32
        self.bin_edges = np.arange(80,3000,100)
        self.fshape, self.fwcs = enmap.fullsky_geometry(res=full_sky_pix*np.pi/180./60., proj="car")
        self.shape = {}
        self.wcs = {}
        self.taper = {}
        self.w2 = {}
        self.w3 = {}
        self.w4 = {}

        self.pix_intermediate = full_sky_pix if (pix_intermediate is None) else pix_intermediate
        self.wdeg = wdeg
        self.hdeg = hdeg

	degree =  u.degree
        vwidth = hdeg/2.
        hwidth = wdeg/2.
	self.pos_south=np.array([[-vwidth+yoffset,-hwidth],[vwidth+yoffset,hwidth]])*degree
	self.pos_eq=np.array([[-vwidth,-hwidth],[vwidth,hwidth]])*degree


        # Get MPI comm
        self.comm = mpi_comm
        try:
            self.rank = mpi_comm.Get_rank()
            self.numcores = mpi_comm.Get_size()
        except:
            self.rank = 0
            self.numcores = 1

        if self.rank==0: 
            self.logger = io.get_logger("rotrecon")

        num_each,each_tasks = mpi_distribute(nsims,self.numcores)
        self.mpibox = MPIStats(self.comm,num_each,tag_start=333)
        if self.rank==0: self.logger.info( "At most "+ str(max(num_each)) + " tasks...")
        self.tasks = each_tasks[self.rank]

        theory_file_root = "data/Aug6_highAcc_CDM"
        powspec_file = "data/Aug6_highAcc_CDM_lenspotentialCls.dat"
        
        self.ps = powspec.read_camb_full_lens(powspec_file).astype(self.dtype)
        self.theory = cmb.loadTheorySpectraFromCAMB(theory_file_root,unlensedEqualsLensed=False,
                                                    useTotal=False,TCMB = 2.7255e6,lpad=9000,get_dimensionless=False)
        self.lmax = lmax
        self.count = 0




    def make_sim(self,seed):

        with bench.show("Lensing operation...") if self.rank==0 else ignore():
            full,kappa = lensing.rand_map(self.fshape, self.fwcs, self.ps, lmax=self.lmax,
                                          maplmax=self.lmax, seed=seed, verbose=True if self.rank==0 else False, dtype=self.dtype,output="lk")

            south = full[0].submap(self.pos_south)
            equator = full[0].submap(self.pos_eq)
            ksouth = kappa.submap(self.pos_south)
            kequator = kappa.submap(self.pos_eq)
            del full
            del kappa

        if self.count==0:
            self.shape['s'], self.wcs['s'] = south.shape, south.wcs
            self.shape['e'], self.wcs['e'] = equator.shape, equator.wcs

            for m in ['s','e']:
                self.taper[m],self.w2[m] = fmaps.get_taper(self.shape[m],taper_percent = 18.0,pad_percent = 4.0,weight=None)
                self.w4[m] = np.mean(self.taper[m]**4.)
                self.w3[m] = np.mean(self.taper[m]**3.)
            
            
            self.rotator = fmaps.MapRotatorEquator(self.shape['s'],self.wcs['s'],self.wdeg,self.hdeg,width_multiplier=0.6,
                                                   height_multiplier=1.2,downsample=True,verbose=True if self.rank==0 else False,
                                                   pix_target_override_arcmin=self.pix_intermediate)

            self.taper['r'] = self.rotator.rotate(self.taper['s'])
            self.w2['r'] = np.mean(self.taper['r']**2.)
            self.w4['r'] = np.mean(self.taper['r']**4.)
            self.w3['r'] = np.mean(self.taper['r']**3.)

            self.shape['r'], self.wcs['r'] = self.rotator.shape_final, self.rotator.wcs_final

            self.fc = {}
            self.binner = {}
            self.modlmap = {}
            for m in ['s','e','r']:
                self.fc[m] = enmap.FourierCalc(self.shape[m],self.wcs[m])
                self.modlmap[m] = enmap.modlmap(self.shape[m],self.wcs[m])
                self.binner[m] = bin2D(self.modlmap[m],self.bin_edges)
            self.cents = self.binner['s'].centers
            self._init_qests()
        
        self.count += 1

        south *= self.taper['s']
        equator *= self.taper['e']
        ksouth *= self.taper['s']
        kequator *= self.taper['e']

        return south,equator,ksouth,kequator

    
    def reconstruct(self,m,imap):
        self.qest[m].updateTEB_X(imap,alreadyFTed=False)
        self.qest[m].updateTEB_Y()
        recon = self.qest[m].getKappa("TT").real
        return recon


    def _init_qests(self):

        
        mlist = ['e','s','r']
        self.qest = {}
        tellminY = 500
        tellmaxY = 3000
        pellminY = 500
        pellmaxY = 3000
        tellminX = 500
        tellmaxX = 3000
        pellminX = 500
        pellmaxX = 3000
        kellmin = 80
        kellmax = 3000
        self.kellmin = kellmin
        self.kellmax = kellmax
        
        for m in mlist:
            lxmap_dat,lymap_dat,modlmap_dat,angmap_dat,lx_dat,ly_dat = fmaps.get_ft_attributes_enmap(self.shape[m],self.wcs[m])
            nT = modlmap_dat.copy()*0.
            nP = modlmap_dat.copy()*0.
            lbeam = modlmap_dat.copy()*0.+1.
            template_dat = fmaps.simple_flipper_template_from_enmap(self.shape[m],self.wcs[m])
            fMaskCMB_TX = fmaps.fourierMask(lx_dat,ly_dat,modlmap_dat,lmin=tellminX,lmax=tellmaxX)
            fMaskCMB_TY = fmaps.fourierMask(lx_dat,ly_dat,modlmap_dat,lmin=tellminY,lmax=tellmaxY)
            fMaskCMB_PX = fmaps.fourierMask(lx_dat,ly_dat,modlmap_dat,lmin=pellminX,lmax=pellmaxX)
            fMaskCMB_PY = fmaps.fourierMask(lx_dat,ly_dat,modlmap_dat,lmin=pellminY,lmax=pellmaxY)
            fMask = fmaps.fourierMask(lx_dat,ly_dat,modlmap_dat,lmin=kellmin,lmax=kellmax)
            with io.nostdout():
                self.qest[m] = Estimator(template_dat,
                                         self.theory,
                                         theorySpectraForNorm=None,
                                         noiseX2dTEB=[nT,nP,nP],
                                         noiseY2dTEB=[nT,nP,nP],
                                         fmaskX2dTEB=[fMaskCMB_TX,fMaskCMB_PX,fMaskCMB_PX],
                                         fmaskY2dTEB=[fMaskCMB_TY,fMaskCMB_PY,fMaskCMB_PY],
                                         fmaskKappa=fMask,
                                         kBeamX = lbeam,
                                         kBeamY = lbeam,
                                         doCurl=False,
                                         TOnly=True,
                                         halo=True,
                                         uEqualsL=True,
                                         gradCut=None,verbose=False,
                                         bigell=self.lmax)

                
    def dump(self):

        def unpack(label,m):
            dic = self.mpibox.stats[label+"-"+m]
            return dic['mean'],dic['errmean']

        mlist = ['s','e','r']

        # CLKK vs input powers
        pl = io.Plotter()
        for m in mlist:
            modlmap = self.modlmap[m]
            clkk = self.binner[m].bin(self.theory.gCl('kk',modlmap))[1]
            pclkk,pclkk_err = unpack("ixi",m)
            pdiff = (pclkk-clkk)/clkk
            perr = pclkk_err/clkk
            pl.addErr(self.cents,pdiff,yerr=perr,label=m,ls="-")
        pl.hline()
        pl.legendOn()
        pl.done(io.dout_dir+"clkkdiff.png")
            

        # CLTT vs input powers
        pl = io.Plotter()
        for m in mlist:
            modlmap = self.modlmap[m]
            cltt = self.binner[m].bin(self.theory.lCl('TT',modlmap))[1]
            pcltt,pcltt_err = unpack("cmb",m)
            pdiff = (pcltt-cltt)/cltt
            perr = pcltt_err/cltt
            pl.addErr(self.cents,pdiff,yerr=perr,label=m,ls="-")
        pl.hline()
        pl.legendOn()
        pl.done(io.dout_dir+"clttdiff.png")



        # RECONSTRUCTION VS CLKK PLOT

        ellrange = np.arange(0,3000)
        clkk = self.theory.gCl("kk",ellrange)

        
        cents = self.cents
        
        for m in mlist:
            modlmap = self.modlmap[m]
            clkk2d = self.theory.gCl('kk',modlmap)

            clkk1d = self.binner[m].bin(clkk2d)[1]
            nlkk = self.binner[m].bin(self.qest[m].N.Nlkk['TT'])[1]
            totkk = self.binner[m].bin(clkk2d+self.qest[m].N.Nlkk['TT'])[1]
            
            pl = io.Plotter(scaleY='log')
            pl.add(ellrange,clkk,color="k",lw=2)
            pl.add(cents,nlkk,ls="--")
            pl.add(cents,totkk,ls="-")
            
            y,err = unpack("rxr",m)
            pl.addErr(cents,y,err,ls="none",marker="o")
            y,err = unpack("rxr-n0",m)
            pl.addErr(cents,y,err,ls="none",marker="o")
            y,err = unpack("rxi",m)
            pl.addErr(cents,y,err,ls="none",marker="o")
            y,err = unpack("ixi",m)
            pl.add(cents,y,ls="none",marker="x",color="k")
            y,err = unpack("n0",m)
            pl.add(cents,y,ls="--")
            pl.add(cents,y+clkk1d,ls="-")
        pl.legendOn()
        pl._ax.set_ylim(1.e-10,1.e-6)
        pl.done(io.dout_dir+"clkkrecon_"+m+".png")
        
        
        # for m in mlist:

        #     modlmap = self.modlmap[m]
        #     cltt = self.theory.lCl('TT',modlmap)
        #     clkk = self.theory.gCl('kk',modlmap)
            
            
        #     unpack("rxr",m)
        #     unpack("rxi",m)
        #     unpack("ixi",m)
        #     unpack("n0",m)
        #     unpack("rxr-n0",m)
            
