import numpy as np
from legume.utils import ftinv
from legume.backend import backend as bd
import legume.constants as cs
import sys
from legume.gme import GuidedModeExp
from legume.exc import ExcitonSchroedEq


class HopfieldPol(object):
    """Main simulation class of the generalized Hopfield matrix method.
    """
    def __init__(self, phc, gmax, truncate_g='abs'):
        """Initialize the Schroedinger equation expansion.
        
        Parameters
        ----------
        phc : PhotCryst
            Photonic crystal object to be simulated.
        gmax : float, optional
            Maximum reciprocal lattice wave-vector length in units of 2pi/a.
        truncate_g : {'tbt', 'abs'}
            Truncation of the reciprocal lattice vectors, ``'tbt'`` takes a 
            parallelogram in reciprocal space, while ``'abs'`` takes a circle.
        """

        self.gme = GuidedModeExp(phc, gmax, truncate_g=truncate_g)

        self.exc_list = []
        for qw in phc.qws:  #loop over blocks of quantum wells added with add_qw
            for ind, z in enumerate(qw.z):  #loop over qws in a single block
                layer_ind = self.gme._z_to_lind(z)
                self.exc_list.append(
                    ExcitonSchroedEq(layer=phc.layers[layer_ind - 1],
                                     z=z,
                                     Vmax=qw.Vmax[ind],
                                     a=qw.a[ind],
                                     M=qw.M[ind],
                                     E0=qw.E0[ind],
                                     loss=qw.loss[ind],
                                     osc_str=qw.osc_str[ind],
                                     gmax=gmax,
                                     truncate_g=truncate_g))

    @property
    def eners(self):
        """Energies of the eigenmodes computed by the Hopfield matrix diagonalisation.
        """
        if self._eners is None: self._eners = []
        return self._eners

    @property
    def eners_im(self):
        """Imaginary part of the frequencies of the eigenmodes computed by the 
        Hopfield matrix diagonalisation.
        """
        if self._eners_im is None: self._eners_im = []
        return self._eners_im

    @property
    def eigvecs(self):
        """Eigenvectors of the eigenmodes computed by the by the Hopfield matrix diagonalisation.
        """
        if self._eigvecs is None: self._eigvecs = []
        return self._eigvecs

    @property
    def fractions_ex(self):
        """Photonic and excitonic fractions of the bands
        """
        if self._fractions_ex is None: self._fractions_ex = []
        return self._fractions_ex

    @property
    def fractions_ph(self):
        """Photonic and excitonic fractions of the bands
        """
        if self._fractions_ph is None: self._fractions_ph = []
        return self._fractions_ph

    @property
    def kpoints(self):
        """Numpy array of shape (2, Nk) with the [kx, ky] coordinates of the 
        k-vectors over which the simulation is run.
        """
        if self._kpoints is None: self._kpoints = []
        return self._kpoints

    @property
    def gvec(self):
        """Numpy array of shape (2, Ng) with the [gx, gy] coordinates of the 
        reciprocal lattice vectors over which the simulation is run.
        """
        if self._gvec is None: self._gvec = []
        return self._gvec

    def _print(self, text, flush=False, end='\n'):
        """Print if verbose==True
            """
        if self.verbose == True:
            if flush == False:
                print(text, end=end)
            else:
                sys.stdout.write("\r" + text)
                sys.stdout.flush()

    def _z_to_lind(self, z):
        """
        Get a layer index corresponding to a position z. Claddings are included 
        as first and last layer
        """

        z_max = self.phc.claddings[0].z_max
        lind = 0  # Index denoting which layer (including claddings) z is in
        while z > z_max and lind < self.N_layers:
            lind += 1
            z_max = self.phc.layers[lind - 1].z_max
        if z > z_max and lind == self.N_layers: lind += 1

        return lind

    def _calculate_fraction(self, eigenvectors):
        """
        Calculate the photonic and excitonic fraction of the bands starting from
        the polaritonic eigenvectors.


         """

        # Not pythonic, could be done better
        num_bands = np.shape(eigenvectors)[1]
        frac_ex = np.zeros((num_bands))
        frac_ph = np.zeros((num_bands))

        for band in range(num_bands):
            frac_ph[band] = np.sum(np.abs(eigenvectors[0:self.N_max,band])**2)\
            +np.sum(np.abs(eigenvectors[self.N_max+self.M_max*self.num_QWs:2*self.N_max+self.M_max*self.num_QWs,band])**2)

            frac_ex[band] = np.sum(np.abs(eigenvectors[self.N_max:self.N_max+self.M_max*self.num_QWs,band])**2)\
            +np.sum(np.abs(eigenvectors[2*self.N_max+self.M_max*self.num_QWs:,band])**2)

        return frac_ex, frac_ph

    def _calculate_C_D(self, exc, kind):
        """C and D blocks of generalized Hopfield matrix,
        see Appendix of https://journals.aps.org/prb/abstract/10.1103/PhysRevB.75.235325,
        here we adopt SI units by adding the factor 1/(4*pi*epsilon_0). The factor 1/sqrt(a)
        comes from the normalisation of the fields and recovers the correct units.

        The input is an ExcitonSchroedEq run from which we recover the oscillator strength, the
        polarization unit vector and the exc. wavefunction. The prefactor of C
        is also multiplied by 1/e to get the energies in eV. Finally, we also recover the Fourier
        components of the Electric field from the GuidedModeExp.

        The Oscillator strength must be converted to 'float'.

         """
        pref = -1j * np.sqrt(cs.hbar**2 * cs.e**2 /
                             (4 * cs.m_e * cs.epsilon_0)) / cs.e / np.sqrt(
                                 self.a)
        C = np.zeros((self.N_max, self.M_max), dtype="complex")
        #n: loop over photonic modes, nu: loop over excitonic modes
        for n in range(self.N_max):
            E_comp = self.gme.ft_field_xy("E", kind=kind, mind=n, z=exc.z)
            for nu in range(self.M_max):
                W_comp = exc.ft_wavef_xy(kind=kind, mind=nu)
                C[n, nu] = pref * np.sum(
                    np.dot(np.sqrt(exc.osc_str.astype(float)), E_comp) *
                    np.conjugate(W_comp))

        D = np.zeros((self.N_max, self.N_max), dtype="complex")
        #n_1, n_2 loop over photonic modes (n and n' in the paper), nu loop over excitonic modes
        for n_1 in range(self.N_max):
            for n_2 in range(self.N_max):
                D[n_1, n_2] = np.sum(
                    np.conjugate(C[n_1, :]) * C[n_2, :] /
                    np.real(exc.eners[kind, :]))

        return C, D

    def _construct_Hopfield(self, kind):
        """ Construct the generalised Hopfield matrix for given k point 

        """

        # Conversion factor: from dimensionless frequency to eV
        self.a = self.exc_list[0].a
        conv_fact = cs.h_eV_Hz * cs.c / (self.a)

        #Initialise the list which contains all the C blocks, and the final D block
        C_blocks = [[] for i in range(self.num_QWs)]
        D_final_block = np.zeros((self.N_max, self.N_max), dtype="complex")

        #Calculate the photonic diagonal block
        diag_phot = np.zeros((self.N_max, self.N_max), dtype="complex")
        if self.gme.symmetry.lower() == 'none' or self.gme.symmetry.lower(
        ) == 'both':
            np.fill_diagonal(
                diag_phot, self.gme.freqs[kind, :] * conv_fact +
                1j * self.gme.freqs_im[kind, :] * conv_fact)
        elif self.gme.symmetry.lower() == 'odd':
            np.fill_diagonal(
                diag_phot, self.gme.freqs_odd[kind, :] * conv_fact +
                1j * self.gme.freqs_im_odd[kind, :] * conv_fact)
        elif self.gme.symmetry.lower() == 'even':
            np.fill_diagonal(
                diag_phot, self.gme.freqs_even[kind, :] * conv_fact +
                1j * self.gme.freqs_im_even[kind, :] * conv_fact)

        for ind_ex, exc_sch in enumerate(self.exc_list):
            C, D = self._calculate_C_D(exc=exc_sch, kind=kind)
            D_final_block = D_final_block + D
            C_blocks[ind_ex] = C

        C_final_block = bd.hstack([c for c in C_blocks])
        C_dagger_final_block = np.conjugate(C_final_block.T)

        #Initialise the excitonic block
        diag_exc = np.zeros(
            (self.M_max * self.num_QWs, self.M_max * self.num_QWs),
            dtype="complex")
        exc_el = np.concatenate(
            [exc_out.eners[kind] for exc_out in self.exc_list])

        np.fill_diagonal(diag_exc, exc_el)

        diag_phot = diag_phot + 2 * bd.real(D_final_block)

        row_0 = np.hstack(
            (diag_phot, -1j * C_final_block, -2 * D, -1j * C_final_block))
        row_1 = np.hstack((1j * C_dagger_final_block, diag_exc,
                           -1j * C_dagger_final_block, diag_exc * 0.))
        row_2 = np.hstack(
            (2 * D, -1j * C_final_block, -diag_phot, -1j * C_final_block))
        row_3 = np.hstack((-1j * C_dagger_final_block, diag_exc * 0.,
                           1j * C_dagger_final_block, -diag_exc))
        M = np.vstack((row_0, row_1, row_2, row_3))

        return M

    def run(self,
            gme_options={},
            exc_options={},
            kpoints: np.ndarray = np.array([[0], [0]]),
            verbose=True):
        """
        Run the simulation. The computed eigen-frequencies are stored in
        :attr:`ExcitonSchroedEq.freqs`, and the corresponding eigenvectors - 
        in :attr:`ExcitonSchroedEq.eigvecs`.
        
        Parameters
        ----------
        kpoints : np.ndarray, optional
            Numpy array of shape (2, Nk) with the [kx, ky] coordinates of the 
            k-vectors over which the simulation is run.
        """
        eners = []
        eners_im = []
        self._kpoints = kpoints
        self._eigvecs = []
        self._fractions_ex = []
        self._fractions_ph = []
        self.verbose = verbose
        self._gvec = self.gme.gvec

        #Force the same kpoints for gme and exc solvers
        gme_options['kpoints'] = self.kpoints
        exc_options['kpoints'] = self.kpoints

        #Run gme
        self.gme.run(**gme_options)

        self.num_QWs = np.shape(self.exc_list)[0]

        #Run all excitonic Sch. equations
        for exc_sch in self.exc_list:
            exc_sch.run(**exc_options)

        #Retrieve number of photonic/excitonic eigenvalues
        self.N_max = self.gme.numeig
        self.M_max = self.exc_list[0].numeig_ex

        for ik, k in enumerate(self._kpoints.T):

            self._print(
                f"Running Hopfield diagonalisation k-point {ik+1} of {self.kpoints.shape[1]}",
                flush=True)
            # Construct the Hopfield matrix for diagonalization in eV

            mat = self._construct_Hopfield(kind=ik)
            self.numeig = np.shape(mat)[0]

            # NB: we shift the matrix by np.eye to avoid problems at the zero-
            # frequency mode at Gamma

            (ener2, evecs) = bd.eig(mat + bd.eye(mat.shape[0]))
            ener1 = ener2 - bd.ones(mat.shape[0])
            #Filter positive energies
            filt_pos = bd.real(ener1) >= 0
            ener1 = ener1[filt_pos]
            evecs = evecs[:, filt_pos]
            fractions_ex, fractions_ph = self._calculate_fraction(evecs)
            i_sort = bd.argsort(ener1)[0:int(
                self.numeig // 2 -
                1)]  #Only keeps np.shape(mat)[0]//2-1 eigenvalue, all positive

            ener = bd.real(ener1[i_sort])
            ener_im = bd.imag(ener1[i_sort])
            evec = evecs[:, i_sort]
            fraction_ex = fractions_ex[i_sort]
            fraction_ph = fractions_ph[i_sort]
            eners.append(ener)
            eners_im.append(ener_im)
            self._eigvecs.append(evec)
            self._fractions_ex.append(fraction_ex)
            self._fractions_ph.append(fraction_ph)

        # Store the energies
        self._fractions_ex = bd.array(self._fractions_ex)
        self._fractions_ph = bd.array(self._fractions_ph)
        self._eners = bd.array(eners)
        self._eners_im = bd.array(eners_im)
        self._eigvecs = bd.array(self._eigvecs)
        self.mat = mat

    def get_wavef_xy(self, kind, mind, z=0, Nx=100, Ny=100):
        """
        Compute the wavefunction in the xy-plane at 
        position z.
        
        Parameters
        ----------
        kind : int
            The field of the mode at `PlaneWaveExp.kpoints[:, kind]` is 
            computed.
        mind : int
            The field of the `mind` mode at that kpoint is computed.
        z : float
            Position of the xy-plane. This doesn't matter for the PWE or EqSchroe, but is 
            added for consistency with the GME definitions.
        Nx : int, optional
            A grid of Nx points in the elementary cell is created.
        Ny : int, optional
            A grid of Ny points in the elementary cell is created.
        
        Returns
        -------
        fi : dict
            A dictionary with the requested components, 'x', 'y', and/or 'z'.
        xgrid : np.ndarray
            The constructed grid in x.
        ygrid : np.ndarray
            The constructed grid in y.
        """

        # Make a grid in the x-y plane
        (xgrid, ygrid) = self.layer.lattice.xy_grid(Nx=Nx, Ny=Ny)

        # Get the wavefunction Fourier components

        ft = self._eigvecs[kind, :, mind]

        fi = ftinv(ft, self.gvec, xgrid, ygrid)

        return (fi, xgrid, ygrid)