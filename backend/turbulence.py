import numpy as np
from abc import ABC, abstractmethod

class TurbulenceModel(ABC):
    """Base turbulence model"""
    def __init__(self, mesh, nu=1e-5):
        self.mesh = mesh
        self.nu = nu  # kinematic viscosity
        self.nu_t = np.zeros(len(mesh.cells))  # turbulent viscosity
    
    @abstractmethod
    def compute(self, velocity_field, k_field=None, epsilon_field=None):
        pass
    
    def get_turbulent_viscosity(self):
        return self.nu_t.copy()
    
    def get_effective_viscosity(self):
        return self.nu + self.nu_t

class LaminarModel(TurbulenceModel):
    """Laminar (no turbulence)"""
    def compute(self, velocity_field, k_field=None, epsilon_field=None):
        self.nu_t = np.zeros(len(self.mesh.cells))
        return self.nu_t

class KEpsilonModel(TurbulenceModel):
    """Standard k-epsilon turbulence model"""
    def __init__(self, mesh, nu=1e-5, C_mu=0.09, C1=1.44, C2=1.92, sigma_k=1.0, sigma_eps=1.3):
        super().__init__(mesh, nu)
        self.C_mu = C_mu
        self.C1 = C1
        self.C2 = C2
        self.sigma_k = sigma_k
        self.sigma_eps = sigma_eps
    
    def compute(self, velocity_field, k_field, epsilon_field):
        """Compute turbulent viscosity from k and epsilon"""
        if k_field is None or epsilon_field is None:
            return np.zeros(len(self.mesh.cells))
        
        k = k_field.data[:, 0]
        epsilon = epsilon_field.data[:, 0]
        
        self.nu_t = self.C_mu * (k**2 / (epsilon + 1e-10))
        return self.nu_t
    
    def production_term(self, strain_rate_tensor):
        """Production of turbulent kinetic energy"""
        S = np.linalg.norm(strain_rate_tensor, axis=1)
        P = self.nu_t * 2 * S**2
        return P
    
    def dissipation_term(self, k_field, epsilon_field):
        """Dissipation of turbulent kinetic energy"""
        k = k_field.data[:, 0]
        epsilon = epsilon_field.data[:, 0]
        return epsilon

class KOmegaModel(TurbulenceModel):
    """k-omega turbulence model"""
    def __init__(self, mesh, nu=1e-5, beta_star=0.09):
        super().__init__(mesh, nu)
        self.beta_star = beta_star
    
    def compute(self, velocity_field, k_field, omega_field):
        """Compute turbulent viscosity from k and omega"""
        if k_field is None or omega_field is None:
            return np.zeros(len(self.mesh.cells))
        
        k = k_field.data[:, 0]
        omega = omega_field.data[:, 0]
        
        self.nu_t = k / (omega + 1e-10)
        return self.nu_t

class SSTKOmegaModel(TurbulenceModel):
    """SST k-omega (Shear Stress Transport)"""
    def __init__(self, mesh, nu=1e-5):
        super().__init__(mesh, nu)
    
    def compute(self, velocity_field, k_field, omega_field):
        """SST model combines k-epsilon in core and k-omega near walls"""
        k = k_field.data[:, 0]
        omega = omega_field.data[:, 0]
        
        F1 = 1.0  # blending function
        self.nu_t = k / (omega + 1e-10) * F1
        return self.nu_t

class SpalartAllmarasModel(TurbulenceModel):
    """Spalart-Allmaras one-equation model"""
    def __init__(self, mesh, nu=1e-5, c_v1=7.1, c_b1=0.1355):
        super().__init__(mesh, nu)
        self.c_v1 = c_v1
        self.c_b1 = c_b1
    
    def compute(self, velocity_field, nu_t_field=None):
        """Compute turbulent viscosity from nu_tilde"""
        if nu_t_field is None:
            return np.zeros(len(self.mesh.cells))
        
        nu_tilde = nu_t_field.data[:, 0]
        fv1 = (nu_tilde**3) / ((nu_tilde**3) + self.c_v1**3)
        self.nu_t = nu_tilde * fv1
        return self.nu_t

class LESModel(TurbulenceModel):
    """Large Eddy Simulation base class"""
    def __init__(self, mesh, nu=1e-5, cs=0.1):
        super().__init__(mesh, nu)
        self.cs = cs  # Smagorinsky constant
    
    def compute(self, velocity_field, filter_width=None):
        """Compute SGS viscosity"""
        if filter_width is None:
            filter_width = (self.mesh.dx * self.mesh.dy * self.mesh.dz)**(1/3)
        
        S = self.compute_strain_rate(velocity_field)
        self.nu_t = (self.cs * filter_width)**2 * np.linalg.norm(S, axis=1)
        return self.nu_t
    
    def compute_strain_rate(self, velocity_field):
        """Compute strain rate tensor"""
        S = np.zeros((len(self.mesh.cells), 3, 3))
        for i in range(len(self.mesh.cells) - 1):
            dui_dxj = np.zeros((3, 3))
            dui_dxj[0, 0] = (velocity_field.data[i+1, 0] - velocity_field.data[i, 0]) / self.mesh.dx
            S[i] = dui_dxj + dui_dxj.T
        return S

class WallFunctions:
    """Wall function for near-wall treatment"""
    
    @staticmethod
    def log_law(u_tau, y, kappa=0.41, b=5.0):
        """Log-law of the wall"""
        y_plus = y * u_tau / (1e-5 + 1e-15)
        if y_plus > 30:
            return (1/kappa) * np.log(y_plus) + b
        else:
            return y_plus
    
    @staticmethod
    def u_tau_from_wall_shear(tau_w, rho=1.0):
        """Friction velocity from wall shear stress"""
        return np.sqrt(np.abs(tau_w) / (rho + 1e-10))
    
    @staticmethod
    def apply_wall_function(velocity, y_wall, u_tau):
        """Apply wall function for velocity"""
        return u_tau * WallFunctions.log_law(u_tau, y_wall)

class TurbulenceProperties:
    """Compute turbulent properties"""
    
    @staticmethod
    def reynolds_number(rho, velocity, length, mu):
        """Reynolds number"""
        return rho * np.linalg.norm(velocity) * length / mu
    
    @staticmethod
    def turbulent_kinetic_energy(velocity_rms):
        """TKE from RMS velocity"""
        return 0.5 * np.sum(velocity_rms**2)
    
    @staticmethod
    def turbulent_length_scale(k, epsilon, c_mu=0.09):
        """Turbulent length scale"""
        return c_mu * (k**1.5) / (epsilon + 1e-10)
    
    @staticmethod
    def turbulent_time_scale(k, epsilon):
        """Turbulent time scale"""
        return k / (epsilon + 1e-10)
