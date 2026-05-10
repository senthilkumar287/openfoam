import numpy as np
from abc import ABC, abstractmethod

class ChemistryModel(ABC):
    """Base chemistry model"""
    def __init__(self, num_species, num_reactions):
        self.num_species = num_species
        self.num_reactions = num_reactions
        self.Y = np.zeros((1, num_species))  # Species mass fractions
        self.T = 300.0  # Temperature
        self.pressure = 101325.0  # Pa
    
    @abstractmethod
    def compute_rates(self, Y, T):
        pass
    
    def get_species_names(self):
        return [f'Y_{i}' for i in range(self.num_species)]

class SimpleChemistry(ChemistryModel):
    """Simple one-step chemistry model"""
    def __init__(self, fuel='CH4', oxidizer='O2', product='CO2'):
        super().__init__(num_species=3, num_reactions=1)
        self.fuel = fuel
        self.oxidizer = oxidizer
        self.product = product
        self.k_ref = 1e6  # Reference reaction rate
        self.Ea = 50000  # Activation energy (J/mol)
        self.R = 8.314  # Gas constant
    
    def compute_rates(self, Y, T):
        """Arrhenius rate"""
        k = self.k_ref * np.exp(-self.Ea / (self.R * T))
        
        # Simple: rate = k * [fuel] * [oxidizer]
        rate = k * Y[0] * Y[1]
        
        return np.array([-rate, -rate * 2, rate * 3])  # stoichiometry

class FlameletModel(ChemistryModel):
    """Flamelet-based combustion model"""
    def __init__(self, num_species=5):
        super().__init__(num_species, num_reactions=1)
        self.mixture_fraction = np.linspace(0, 1, 100)  # Look-up table parameter
        self.stoichiometric_mixture_fraction = 0.055
    
    def compute_rates(self, Y, T, mixture_fraction):
        """Compute species from mixture fraction"""
        # Interpolate from flamelet table
        rates = np.zeros(self.num_species)
        return rates

class NoxyGenerator:
    """NOx formation models"""
    
    @staticmethod
    def thermal_nox(T, residence_time, O2_fraction=0.21):
        """Thermal NOx (Zeldovich mechanism)"""
        if T > 1800:  # Only forms at high T
            nox = 1e-6 * residence_time * O2_fraction * np.exp(-69000 / (1.987 * T))
            return np.clip(nox, 0, 1)
        return 0.0
    
    @staticmethod
    def prompt_nox(T, CH_radical, O2_fraction):
        """Prompt NOx"""
        if T > 1500:
            nox = 1e-8 * CH_radical * O2_fraction
            return np.clip(nox, 0, 1)
        return 0.0

class SootModel:
    """Soot formation and burnout"""
    
    @staticmethod
    def nucleation_rate(T, precursor_concentration):
        """Soot nucleation rate"""
        if T > 1400:
            rate = 1e5 * precursor_concentration * np.exp(-150000 / (8.314 * T))
            return rate
        return 0.0
    
    @staticmethod
    def growth_rate(soot_mass, T, oxidizer):
        """Soot surface growth"""
        growth = soot_mass * oxidizer * np.exp(-100000 / (8.314 * T))
        return growth
    
    @staticmethod
    def oxidation_rate(soot_mass, T, O2):
        """Soot oxidation"""
        oxidation = soot_mass * O2 * np.exp(-150000 / (8.314 * T))
        return oxidation

class ReactionMechanism:
    """Chemical reaction mechanism"""
    
    def __init__(self, species_list, reactions_list):
        self.species = species_list
        self.reactions = reactions_list
        self.num_species = len(species_list)
        self.num_reactions = len(reactions_list)
    
    def compute_source_terms(self, Y, T):
        """Compute chemical source terms for each species"""
        source = np.zeros(self.num_species)
        
        for rxn in self.reactions:
            k = rxn['k_ref'] * np.exp(-rxn['Ea'] / (8.314 * T))
            
            # Compute reactant concentrations
            reactant_conc = 1.0
            for reactant in rxn['reactants']:
                idx = self.species.index(reactant)
                reactant_conc *= Y[idx]
            
            rate = k * reactant_conc
            
            # Add to products and subtract from reactants
            for reactant in rxn['reactants']:
                idx = self.species.index(reactant)
                source[idx] -= rate
            
            for product in rxn['products']:
                idx = self.species.index(product)
                source[idx] += rate
        
        return source

class CombustionSolver:
    """Combustion with chemistry coupling"""
    
    def __init__(self, mesh, chemistry_model):
        self.mesh = mesh
        self.chemistry = chemistry_model
        self.Y = np.zeros((len(mesh.cells), chemistry_model.num_species))
        self.T = np.ones(len(mesh.cells)) * 300.0
        self.dt = 0.001
    
    def solve_chemistry(self, max_substeps=100):
        """Solve chemistry ODE (operator splitting)"""
        
        for step in range(max_substeps):
            for cell_idx in range(len(self.mesh.cells)):
                Y_cell = self.Y[cell_idx]
                T_cell = self.T[cell_idx]
                
                # Compute rates
                dY_dt = self.chemistry.compute_rates(Y_cell, T_cell)
                
                # Simple Euler step
                self.Y[cell_idx] += dY_dt * self.dt
                
                # Ensure non-negative
                self.Y[cell_idx] = np.maximum(self.Y[cell_idx], 0)
                
                # Ensure sum = 1 (mass fraction constraint)
                sum_Y = np.sum(self.Y[cell_idx])
                if sum_Y > 0:
                    self.Y[cell_idx] /= sum_Y
    
    def compute_heat_release(self):
        """Heat release rate from combustion"""
        HoC = 50e6  # Heat of combustion (J/kg fuel)
        fuel_burned = 1e-6  # Simplified
        q = HoC * fuel_burned
        return np.ones(len(self.mesh.cells)) * q

class ThermodynamicProperties:
    """Thermodynamic property tables"""
    
    @staticmethod
    def specific_heat_capacity(T, species='air'):
        """Cp as function of temperature"""
        if species == 'air':
            Cp = 1000 + 0.2 * T
        elif species == 'H2O':
            Cp = 1200 + 0.5 * T
        else:
            Cp = 1000
        return Cp
    
    @staticmethod
    def viscosity(T, species='air'):
        """Dynamic viscosity (Sutherland's law)"""
        if species == 'air':
            mu0 = 1.81e-5
            T0 = 288.15
            S = 110.4
            mu = mu0 * (T / T0)**1.5 * (T0 + S) / (T + S)
        else:
            mu = 1e-5
        return mu
    
    @staticmethod
    def thermal_conductivity(T, species='air'):
        """Thermal conductivity"""
        if species == 'air':
            k = 0.02 + 0.00007 * T
        else:
            k = 0.026
        return k
    
    @staticmethod
    def enthalpy(T, species='air', T_ref=298):
        """Specific enthalpy"""
        Cp = ThermodynamicProperties.specific_heat_capacity(T, species)
        H = Cp * (T - T_ref)
        return H

class EquationOfState:
    """Equation of state"""
    
    @staticmethod
    def ideal_gas(rho, T, R=287):
        """Ideal gas law: p = ρ * R * T"""
        return rho * R * T
    
    @staticmethod
    def density_from_pressure(p, T, R=287):
        """Density from pressure and temperature"""
        return p / (R * T)
    
    @staticmethod
    def mach_number(velocity, T, gamma=1.4, R=287):
        """Mach number from velocity and temperature"""
        a = np.sqrt(gamma * R * T)  # Speed of sound
        return velocity / a
