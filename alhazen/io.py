import sys
from enlib import enmap
import numpy as np
import orphics.analysis.flatMaps as fmaps

def enmaps_from_config(Config,sim_section,analysis_section,pol=False):
    """
    Algorithm for deciding sim and analysis shapes and wcs:

    Check if user has specified a *data* template
        * If yes, use its shape and wcs for the data
        - Determine ratio simpixel/anpixel
        - Upsample by that ratio to make sim template
        * If no, 

    """
    
    pixel_sim = Config.getfloat(sim_section,"pixel_arcmin")
    buffer_sim = Config.getfloat(sim_section,"buffer")
    try:
        pt_file = Config.get(analysis_section,"patch_template")
        imap = enmap.read_map(pt_file)
        shape_dat = imap.shape
        wcs_dat = imap.wcs
    except:
        pixel_analysis = Config.getfloat(analysis_section,"pixel_arcmin")
        width_analysis_deg = Config.getfloat(analysis_section,"patch_degrees_width")
        height_analysis_deg = Config.getfloat(analysis_section,"patch_degrees_height")
        ra_offset = Config.getfloat(analysis_section,"ra_offset")
        dec_offset = Config.getfloat(analysis_section,"dec_offset")
        projection = Config.get(analysis_section,"projection")


        
        shape_dat, wcs_dat = enmap.get_enmap_patch(width_analysis_deg*60.,pixel_analysis,proj=projection,pol=pol,height_arcmin=height_analysis_deg*60.,xoffset_degree=ra_offset,yoffset_degree=dec_offset)

        if np.abs(buffer_sim-1.)<1.e-3:
            shape_sim, wcs_sim = enmap.get_enmap_patch(width_analysis_deg*60.,pixel_sim,proj=projection,pol=pol,height_arcmin=height_analysis_deg*60.,xoffset_degree=ra_offset,yoffset_degree=dec_offset)
        else:
            raise NotImplementedError, "Buffer !=1 not implemented"

    return shape_sim, wcs_sim, shape_dat, wcs_dat            

def patch_array_from_config(Config,exp_name,shape,wcs,dimensionless=False,TCMB=2.7255e6):
    pa = fmaps.PatchArray(shape,wcs,skip_real=False)
    try:
        bfile = Config.get(exp_name,"beam_file")
        ells,bls = np.loadtxt(bfile,delimiter=",",unpack=True,use_cols=[0,1])
        pa.add_1d_beam(ells,bls,fill_value="extrapolate")
    except:
        fwhm = Config.getfloat(exp_name,"beam")
        pa.add_gaussian_beam(fwhm)

    try:
        n2d_file_T = Config.get(exp_name,"noise_2d_file_T")
        n2d_file_P = Config.get(exp_name,"noise_2d_file_P")
        imapT = enmap.read_map(n2d_file_T)
        imapP = enmap.read_map(n2d_file_P)
        pa.add_noise_2d(nT=imapT,nP=imapP)
    except:
        noise_T = Config.getfloat(exp_name,"noise_T")
        noise_P = Config.getfloat(exp_name,"noise_P")
        lknee_T = Config.getfloat(exp_name,"lknee_T")
        lknee_P = Config.getfloat(exp_name,"lknee_P")
        alpha_T = Config.getfloat(exp_name,"alpha_T")
        alpha_P = Config.getfloat(exp_name,"alpha_P")

        pa.add_white_noise_with_atm(noise_T,noise_P,lknee_T,alpha_T,lknee_P,alpha_P,map_dimensionless=dimensionless,TCMB=TCMB)


    return pa


def get_patch_degrees(Config,section):

    try:
        patch_arcmins = Config.getfloat(section,"patch_arcmins")
        arcmin = True
    except:
        arcmin = False

    try:
        patch_degrees = Config.getfloat(section,"patch_degrees")
        degree = True
    except:
        degree = False


    if arcmin and degree:
        raise ValueError
    elif arcmin:
        return patch_arcmins/60.
    elif degree:
        return patch_degrees
    else:
        print "ERROR: Patch width not specified."
        sys.exit()

    

def ellbounds_from_config(Config,recon_section):
    ret = []
    for rval in ["lmax","tellmin","tellmax","pellmin","pellmax","kellmin","kellmax"]:
        ret.append(Config.getint(recon_section,rval))

    return ret
    
