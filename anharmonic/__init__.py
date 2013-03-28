import sys
import phonopy.structure.spglib as spg
import numpy as np
from anharmonic.q2v import PhononPhonon
from anharmonic.im_self_energy import ImSelfEnergy
from anharmonic.linewidth import Linewidth
from anharmonic.BTE_RTA import BTE_RTA
from anharmonic.jointDOS import get_jointDOS
from anharmonic.gruneisen import Gruneisen
import anharmonic.triplets as triplets
from anharmonic.file_IO import write_kappa, parse_gamma

class JointDOS:
    def __init__(self,
                 supercell=None,
                 primitive=None,
                 mesh=None,
                 fc2=None,
                 nac_params=None,
                 sigma=None,
                 omega_step=None,
                 factor=None,
                 freq_factor=None,
                 freq_scale=None,
                 is_nosym=False,
                 symprec=1e-5,
                 log_level=0):
        self._supercell = supercell
        self._primitive = primitive
        self._mesh = mesh
        self._fc2 = fc2
        self._nac_params = nac_params
        self._sigma = sigma
        self._omega_step = omega_step
        self._factor = factor
        self._freq_factor = freq_factor
        self._freq_scale = freq_scale
        self._is_nosym = is_nosym
        self._symprec = symprec
        self._log_level = log_level

    def get_jointDOS(self, grid_points, filename=None):
        get_jointDOS(grid_points,
                     self._mesh,
                     self._primitive,
                     self._supercell,
                     self._fc2,
                     self._nac_params,
                     self._sigma,
                     self._omega_step,
                     self._factor,
                     self._freq_factor,
                     self._freq_scale,
                     self._is_nosym,
                     self._symprec,
                     filename,
                     self._log_level)

class Phono3py:
    def __init__(self,
                 supercell=None,
                 primitive=None,
                 mesh=None,
                 fc3=None,
                 factor=None,
                 freq_factor=None,
                 is_nosym=False,
                 is_symmetrize_fc3_q=False,
                 is_read_triplets=False,
                 r2q_TI_index=None,
                 is_Peierls=False,
                 symprec=1e-5,
                 log_level=0):

        self._supercell = supercell
        self._primitive = primitive
        self._mesh = mesh
        self._fc3 = fc3
        self._factor = factor
        self._freq_factor = freq_factor
        self._is_nosym = is_nosym
        self._is_symmetrize_fc3_q = is_symmetrize_fc3_q
        self._symprec = symprec
        self._log_level = log_level
        self._is_read_triplets = is_read_triplets
        self._r2q_TI_index = r2q_TI_index
        self._is_Peierls = is_Peierls
        self._kappas = None
        self._gammas = None

        self._pp = PhononPhonon(fc3,
                                supercell,
                                primitive,
                                mesh,
                                factor=self._factor,
                                freq_factor=self._freq_factor,
                                symprec=self._symprec,
                                is_read_triplets=self._is_read_triplets,
                                r2q_TI_index=self._r2q_TI_index,
                                is_symmetrize_fc3_q=self._is_symmetrize_fc3_q,
                                is_Peierls=self._is_Peierls,
                                log_level=self._log_level,
                                is_nosym=self._is_nosym)
        
    def set_dynamical_matrix(self,
                             fc2,
                             supercell,
                             primitive,
                             nac_params=None,
                             nac_q_direction=None,
                             frequency_scale_factor=None):
        self._pp.set_dynamical_matrix(
            fc2,
            supercell,
            primitive,
            nac_params=nac_params,
            nac_q_direction=nac_q_direction,
            frequency_scale_factor=frequency_scale_factor)
                           
    def get_damping_function(self,
                             grid_points,
                             sets_of_band_indices,
                             sigmas=[0.1],
                             frequency_step=None,
                             temperatures=[None],
                             filename=None,
                             gamma_option=0):
        self._im_self_energy = ImSelfEnergy(self._pp,
                                            sigmas=sigmas,
                                            frequency_step=frequency_step,
                                            temperatures=temperatures,
                                            gamma_option=gamma_option,
                                            filename=filename,
                                            log_level=self._log_level)

        if grid_points is None:
            print "Grid points are not specified."
            return False

        for gp in grid_points:
            self._pp.set_triplets_at_q(gp)

            if sets_of_band_indices is None:
                if gp==0:
                    self._pp.set_interaction_strength(
                        range(3, self._primitive.get_number_of_atoms() * 3))
                else:
                    self._pp.set_interaction_strength(
                        range(self._primitive.get_number_of_atoms() * 3))

            else:
                for band_indices in sets_of_band_indices:
                    self._pp.set_interaction_strength(band_indices)
                    self._im_self_energy.get_damping_function()

    def get_linewidth(self,
                      grid_points,
                      sets_of_band_indices,
                      sigmas=[0.1],
                      t_max=1500,
                      t_min=0,
                      t_step=10,
                      gamma_option=0,
                      filename=None):

        lw = Linewidth(self._pp,
                       sigmas=sigmas,
                       t_max=t_max,
                       t_min=t_min,
                       t_step=t_step)
        
        if grid_points is None:
            print "Grid points are not specified."
            return False

        if sets_of_band_indices is None:
            print "Band indices are not specified."
            return False

        for gp in grid_points:
            self._pp.set_triplets_at_q(gp)
            for band_indices in sets_of_band_indices:
                self._pp.set_interaction_strength(band_indices)
                fwhms_sigmas, freqs_sigmas = lw.get_linewidth(
                    filename=filename)
                temps = lw.get_temperatures()

                for sigma, fwhms, freqs in zip(
                    sigmas, fwhms_sigmas, freqs_sigmas):
                    print "# Grid point:", gp
                    print "# Sigma:", sigma
                    print "# Frequencies:", freqs
                    for fwhm, t in zip(fwhms.T, temps):
                        print t, fwhm
                    print

    def get_thermal_conductivity(self,
                                 sigmas=[0.1],
                                 t_max=1500,
                                 t_min=0,
                                 t_step=10,
                                 max_freepath=0.01, # in meter
                                 grid_points=None,
                                 mesh_divisors=None,
                                 no_kappa_stars=False,
                                 read_gammas=False,
                                 gamma_option=0,
                                 filename=None):

        lt = BTE_RTA(self._pp,
                     sigmas=sigmas,
                     t_max=t_max,
                     t_min=t_min,
                     t_step=t_step,
                     max_freepath=max_freepath,
                     mesh_divisors=mesh_divisors,
                     no_kappa_stars=no_kappa_stars,
                     gamma_option=gamma_option,
                     log_level=self._log_level,
                     write_logs=(not read_gammas),
                     filename=filename)
        lt.set_grid_points(grid_points)

        if read_gammas:
            gammas = np.zeros(
                (1,
                 len(lt.get_grid_address()),
                 len(lt.get_temperatures()),
                 self._primitive.get_number_of_atoms() * 3),
                dtype=float)

            for i, gp in enumerate(lt.get_grid_address()):
                kappa_filename = "kappa"
                suffix = "-m%d%d%d" % tuple(self._mesh)
                if (lt.get_mesh_divisors() != 1).any():
                    suffix += "-d%d%d%d" % tuple(lt.get_mesh_divisors())
                sigma_str = ("%f" % sigmas[0]).rstrip('0').rstrip('\.')
                suffix += ("-g%d" % gp)
                suffix += "-s" + sigma_str
                if filename is not None:
                    suffix += "." + filename
                suffix += ".dat"
                kappa_filename += suffix
                gammas[0, i] = parse_gamma(kappa_filename)[1]
            lt.set_gamma(gammas)
        
        kappas, gammas = lt.get_kappa() # [sigma, grid_point, temperature]
        
        self._kappas = kappas
        self._gammas = gammas

        for t, k in zip(lt.get_temperatures(), kappas[0].sum(axis=0).sum(axis=1)):
            print t, k
                
    # def get_decay_channels(self,
    #                        grid_points,
    #                        sets_of_band_indices,
    #                        temperature=None):

    #     if grid_points==None:
    #         print "Grid points are not specified."
    #         return False

    #     if sets_of_band_indices==None:
    #         print "Band indices are not specified."
    #         return False

    #     for gp in grid_points:
    #         self._pp.set_triplets_at_q(gp)
    #         for band_indices in sets_of_band_indices:
    #             self._pp.set_interaction_strength(band_indices)
    #             self._pp.get_decay_channels(temperature)

    def solve_dynamical_matrix(self, q):
        """Only for test phonopy zheev wrapper"""
        import anharmonic._phono3py as phono3c
        dm = self._pp.get_dynamical_matrix()
        dm.set_dynamical_matrix(q)
        dynmat = dm.get_dynamical_matrix()
        eigvals = np.zeros(len(dynmat), dtype=float)
        phono3c.zheev(dynmat, eigvals)
        
        for f, row in zip(np.sqrt(abs(eigvals)) * self._factor *
                          np.sign(eigvals), dynmat.T):
            print f
            print row
        

    
def get_gruneisen_parameters(fc2,
                             fc3,
                             supercell,
                             primitive,
                             factor=None,
                             is_ion_clamped=False,
                             symprec=1e-5):
    return Gruneisen(fc2,
                     fc3,
                     supercell,
                     primitive,
                     factor=factor,
                     is_ion_clamped=is_ion_clamped,
                     symprec=symprec)

def get_ir_grid_points(mesh, primitive):
    return triplets.get_ir_grid_points(mesh, primitive)
