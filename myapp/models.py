from django.db import models
from CoolProp.CoolProp import PropsSI
import json
import math
from shapely.geometry import Point, Polygon
from scipy.optimize import fsolve


class Compressor(models.Model):
    name = models.CharField(max_length=100)
    displacement_50Hz = models.FloatField()  # m³/h at 1450 rpm
    displacement_60Hz = models.FloatField()  # m³/h at 1750 rpm
    max_pressure_lp = models.FloatField()  # Max low pressure in bar
    max_pressure_hp = models.FloatField()  # Max high pressure in bar
    discharge_conn = models.FloatField()  # connection discharge
    suction_conn = models.FloatField()  # connection suction
    oil_conn = models.FloatField()  # connection oil
    refrigerants = models.JSONField()  # List of refrigerants
    working_field_points = models.JSONField(
        help_text='List of working field points as JSON in Celsius, e.g., [{"T_evap": 0, "T_cond": 40}, ...]'
    )
    additional_constraints = models.JSONField(
        help_text='Additional constraints as JSON in Celsius, e.g., [{"field_points": [{"T_evap": 7, "T_cond": 40}, ...], "message": "Constraint message"}]'
    )

    @staticmethod
    def convert_temperatures_to_kelvin(data):
        """Convert temperatures in data from Celsius to Kelvin."""
        for point in data:
            if 'T_evap' in point and 'T_cond' in point:
                point['T_evap'] += 273.15
                point['T_cond'] += 273.15
        return data

    def save(self, *args, **kwargs):
        # Ensure working_field_points are in Celsius
        if isinstance(self.working_field_points, str):
            self.working_field_points = json.loads(self.working_field_points)

        # Ensure additional_constraints are in Celsius
        if isinstance(self.additional_constraints, str):
            self.additional_constraints = json.loads(self.additional_constraints)

        super().save(*args, **kwargs)  # Save the object with temperatures in Celsius


    def calculate_displacement(self, frequency):
        """Calculate displacement based on frequency."""
        displacement_50Hz = self.displacement_50Hz
        displacement_60Hz = self.displacement_60Hz
        return displacement_50Hz + (frequency - 50) * (displacement_60Hz - displacement_50Hz) / (60 - 50)


    def is_within_working_field(self, T_evap, T_cond):
        """Check if the given temperatures are within the working field."""
        points = [(point['T_evap'], point['T_cond']) for point in
                  self.convert_temperatures_to_kelvin(self.working_field_points.copy())]
        polygon = Polygon(points)
        return polygon.contains(Point(T_evap + 273.15, T_cond + 273.15))

    def check_additional_constraints(self, T_evap, T_cond):
        """Check if the given temperatures satisfy additional constraints."""
        constraints = self.convert_temperatures_to_kelvin(self.additional_constraints.copy())
        warnings = []
        for constraint in constraints:
            field_points = [(point['T_evap'], point['T_cond']) for point in constraint["field_points"]]
            polygon = Polygon(field_points)
            if polygon.contains(Point(T_evap + 273.15, T_cond + 273.15)):
                warnings.append(constraint["message"])
        return warnings

    def is_suitable(self, Q, T_evap, T_cond, frequency, refrigerant, pressure, **kwargs):
        """Determine if the compressor is suitable based on the given parameters."""
        # Ensure the refrigerant is valid
        if refrigerant not in self.refrigerants:
            return False, None  # Refrigerant not suitable

        # Ensure operating conditions are within the working field
        if not self.is_within_working_field(T_evap, T_cond):
            return False, None  # Conditions not within working field

        # Calculate q_compressor using the provided parameters
        q_compressor = self.calculate_q_compressor(frequency, refrigerant, T_evap, T_cond)

        # Compare calculated q_compressor with the required Q
        is_suitable = q_compressor >= Q

        # Return suitability and the calculated cooling capacity
        return is_suitable, q_compressor

    def calculate_mass_flow_rate(self, frequency, refrigerant, T_evap, superheat):
        """Calculate the cooling capacity (q_compressor) based on the given parameters."""
        try:
            # Displacement in m³/h
            displacement = self.calculate_displacement(frequency)
            print(f"Displacement (m³/h): {displacement}")

            # Convert displacement to m³/s
            displacement_m3_s = displacement / 3600
            print(f"Displacement (m³/s): {displacement_m3_s}")

            # Adjust evaporating temperature for superheat
            T_evap_superheat = T_evap + superheat

            # Get density in kg/m³ at evaporating temperature (vapor phase)
            density = PropsSI('D', 'T', T_evap_superheat + 273.15, 'Q', 1, refrigerant)  # Vapor phase
            print(f"Density (kg/m³): {density}")


            # Calculate mass flow rate in kg/s
            mass_flow_rate = displacement_m3_s * density
            return mass_flow_rate

        except Exception as e:
            print(f"Error in calculate_q_compressor: {e}")
            return None


    @staticmethod
    def calculate_gamma(refrigerant, T_evap_superheat):
        """Calculate the adiabatic index (γ) for a given refrigerant and temperature."""
        try:
            cp = PropsSI('Cpmass', 'T', T_evap_superheat + 273.15, 'Q', 1, refrigerant)
            cv = PropsSI('Cvmass', 'T', T_evap_superheat + 273.15, 'Q', 1, refrigerant)
            gamma = cp / cv
            return gamma
        except Exception as e:
            print(f"Error in calculate_gamma: {e}")
            return None

    def calculate_q_compressor(self, frequency, refrigerant, T_evap, T_cond, subcooling, superheat):
        """Calculate the cooling capacity (q_compressor) based on the given parameters."""
        try:
            # Displacement in m³/h
            displacement = self.calculate_displacement(frequency)
            print(f"Displacement (m³/h): {displacement}")

            # Convert displacement to m³/s
            displacement_m3_s = displacement / 3600
            print(f"Displacement (m³/s): {displacement_m3_s}")

            # Adjust evaporating temperature for superheat
            T_evap_superheat = T_evap + superheat

            # Adjust condensing temperature for subcooling
            T_cond_subcooling = T_cond - subcooling

            # Get density in kg/m³ at evaporating temperature (vapor phase)
            pressure_evap = PropsSI('P', 'T', (T_evap + 273.15), 'Q', 1, refrigerant)
            density = PropsSI('D', 'T', (T_evap_superheat + 273.15), 'P', pressure_evap, refrigerant)
            print(f"Density (kg/m³): {density}")


            # Calculate mass flow rate in kg/s
            mass_flow_rate = displacement_m3_s * density
            print(f"Mass flow rate (kg/s): {mass_flow_rate}")

            # Get enthalpy values in kJ/kg
            h_evap = PropsSI('H', 'T', T_evap_superheat + 273.15, 'Q', 1,
                             refrigerant) / 1000  # kJ/kg, vapor phase at evaporating temperature with superheat
            h_cond = PropsSI('H', 'T', T_cond_subcooling + 273.15, 'Q', 0,
                             refrigerant) / 1000  # kJ/kg, liquid phase at condensing temperature with subcooling
            print(f"Enthalpy at evaporation (kJ/kg): {h_evap}")
            print(f"Enthalpy at condensation (kJ/kg): {h_cond}")

            # Calculate pressures
            pressure_suction = PropsSI('P', 'T', T_evap + 273.15, 'Q', 1, refrigerant)
            pressure_discharge = PropsSI('P', 'T', T_cond + 273.15, 'Q', 0, refrigerant)
            print(f"Suction pressure (Pa): {pressure_suction}")
            print(f"Discharge pressure (Pa): {pressure_discharge}")

            # Calculate gamma
            gamma = self.calculate_gamma(refrigerant, T_evap_superheat)
            print(f"Aproximate Gamma do not trust(γ): {gamma}")

            # Estimate discharge temperature
            T_discharge = (T_evap_superheat + 273.15) * (pressure_discharge / pressure_suction) ** ((gamma - 1) / gamma) - 273.15
            print(f"Estimated discharge temperature (°C): {T_discharge}")
            density_discharge = PropsSI('D', 'T', T_discharge + 273.15, 'Q', 1, refrigerant)

            # Calculate q_compressor in kW
            q_compressor = mass_flow_rate * (h_evap - h_cond)  # kW
            print(f"Cooling capacity (kW): {q_compressor}")

            return q_compressor, T_discharge, mass_flow_rate

        except Exception as e:
            print(f"Error in calculate_q_compressor: {e}")
            return None

    def __str__(self):
        return self.name

class Piping(models.Model):
    PIPE_TYPE_CHOICES = [
        ('discharge', 'Discharge Line'),
        ('liquid', 'Liquid Line'),
        ('condensing', 'Condensing Line'),
        ('suction', 'Suction Line'),
        ('oil', 'Oil Line'),
    ]

    name = models.CharField(max_length=100)
    inner_diameter = models.FloatField()
    outer_diameter = models.FloatField()
    material = models.CharField(max_length=50)
    pipe_type = models.CharField(max_length=20, choices=PIPE_TYPE_CHOICES)

    @staticmethod
    def calculate_velocity(mass_flow_rate, inner_diameter, density):
        """Calculate the velocity of the refrigerant in the pipe."""
        # Convert inner diameter from mm to meters
        inner_diameter_m = inner_diameter / 1000
        # Cross-sectional area in square meters
        area = math.pi * (inner_diameter_m / 2) ** 2
        # Velocity in meters per second
        velocity = mass_flow_rate / (density * area)
        print(f"mass flow rate:{mass_flow_rate}")
        print(f"density:{density}")
        print(f"area:{area}")
        print(f"velocity:{velocity}")
        return velocity

    @staticmethod
    def find_best_pipe(pipe_type, mass_flow_rate, density, target_velocity, available_pipes):
        """Find the best pipe for the given pipe type (suction/discharge) based on velocity."""
        best_pipe = None
        min_diff = float('inf')

        for pipe in available_pipes:
            if pipe.pipe_type != pipe_type:
                continue

            velocity = Piping.calculate_velocity(mass_flow_rate, pipe.inner_diameter, density)
            diff = abs(velocity - target_velocity)

            if diff < min_diff:
                min_diff = diff
                best_pipe = pipe

        return best_pipe

    @staticmethod
    def calculate_pressure_drop(pipe_length, temperature, diameter, velocity, pressure, density, refrigerant):
        """Calculate the pressure drop in the pipe using the Darcy-Weisbach equation."""
        # Convert diameter from mm to meters
        diameter_m = diameter / 1000.0

        # Define roughness for copper
        roughness_copper = 0.0015

        # Slightly increase pressure to avoid numerical issues, seems to be uselees now
        pressure_up = pressure

        # Get the viscosity from CoolProp
        viscosity = PropsSI('viscosity', 'T', temperature + 273.15, 'P', pressure_up, refrigerant)

        # Calculate Reynolds number
        reynolds = (density * velocity * diameter_m) / viscosity

        def CalculateF(diameter_m, roughness_copper, reynolds):
            friction = 0.08  # Starting Friction Factor
            while 1:
                leftF = 1 / friction ** 0.5  # Solve Left side of Eqn
                rightF = - 2 * math.log10(
                    2.51 / (reynolds * friction ** 0.5) + (roughness_copper / 1000) / (
                                3.72 * diameter_m))  # Solve Right side of Eqn
                friction = friction - 0.000001  # Change Friction Factor
                #  print(leftF)
                #  print(rightF)
                #  print(friction)
                if (rightF - leftF <= 0):  # Check if Left = Right
                    break
            return friction

        def SwameeJain(diameter_m, roughness_copper, reynolds):
            return 0.25 / (math.log10((roughness_copper / 1000) / (3.7 * diameter_m) + 5.74 / (reynolds ** 0.9))) ** 2

        CWFriction = CalculateF(diameter_m, roughness_copper, reynolds)
        SJFriction = SwameeJain(diameter_m, roughness_copper, reynolds)

        # Print results in nice 'table'
        print("\n---------------RESULTS----------------")
        print("Reynolds Number\t|\t{:.0f}".format(reynolds))
        print("Velocity \t|\t{:.2f}\t(m/s)".format(velocity))
        print("------------FRICTION FACTOR-----------")
        print("Colebrook-White\t|\t{:.4f}".format(CWFriction))
        print("Swamee-Jain\t|\t{:.4f}".format(SJFriction))

        # Calculate pressure drop in Pascals
        pressure_drop = SJFriction * (pipe_length / diameter_m) * (density * velocity ** 2) / 2

        # For debugging purposes
        print(f"Diameter (m): {diameter_m}")
        print(f"Viscosity (Pa.s): {viscosity}")
        print(f"Reynolds number: {reynolds}")
        print(f"Friction factor: {SJFriction}")
        print(f"pressure drop {pressure_drop}")

        return pressure_drop

    @staticmethod
    def get_density(temperature, refrigerant, pressure):
        """Get the density of the refrigerant at the specified temperature."""
        # return PropsSI('D', 'T', temperature + 273.15, 'Q', 1, refrigerant)
        return PropsSI('D', 'T', (temperature + 273.15), 'P', pressure, refrigerant)

    @staticmethod
    def pipe_parameters(refrigerant, T_evap, T_discharge, mass_flow_rate, pipe_length, T_cond,superheat, subcooling, inner_diameter):
        """Get the best pipes for the suction and discharge lines based on the given parameters."""
        pressure_discharge = PropsSI('P', 'T', (T_cond + 273.15), 'Q', 0, refrigerant)
        pressure_suction = PropsSI('P', 'T', (T_evap + 273.15), 'Q', 1, refrigerant) * 1.01

        density_suction = Piping.get_density(T_evap + superheat + 0.5, refrigerant,pressure_suction)  # Density at suction
        density_discharge = Piping.get_density(T_discharge, refrigerant, pressure_discharge)  # Density at discharge


        velocity_discharge = Piping.calculate_velocity(mass_flow_rate, inner_diameter, density_discharge)
        pressure_drop_discharge = Piping.calculate_pressure_drop(pipe_length, T_discharge,inner_diameter, velocity_discharge,pressure_discharge, density_discharge, refrigerant)

        velocity_suction = Piping.calculate_velocity(mass_flow_rate, inner_diameter, density_suction)
        pressure_drop_suction = Piping.calculate_pressure_drop(pipe_length, T_evap, inner_diameter, velocity_suction, pressure_suction, density_suction,refrigerant)

        return velocity_suction, pressure_drop_suction, velocity_discharge, pressure_drop_discharge

    @staticmethod
    def get_best_pipes(refrigerant, T_evap, T_discharge, mass_flow_rate, pipe_length, available_pipes, T_cond,superheat , subcooling):
        """Get the best pipes for the suction and discharge lines based on the given parameters."""
        # density_suction = Piping.get_density(T_evap+10 , refrigerant)  # Density at suction
        # density_discharge = Piping.get_density(T_discharge, refrigerant)  # Density at discharge
        print(f"tevap {T_evap}")
        print(f"tcond {T_cond}")
        print(f"tdisch {T_discharge}")
        pressure_discharge = PropsSI('P', 'T', (T_cond + 273.15), 'Q', 0, refrigerant)
        pressure_suction = PropsSI('P', 'T', (T_evap + 273.15), 'Q', 1, refrigerant)*1.01
        print(f"pressure suction{pressure_suction}")
        print(f"pressure discharge{pressure_discharge}")

        density_suction = Piping.get_density(T_evap +superheat+0.5, refrigerant, pressure_suction)  # Density at suction
        density_discharge = Piping.get_density(T_discharge , refrigerant, pressure_discharge)  # Density at discharge

        suction_pipe = Piping.find_best_pipe('suction', mass_flow_rate, density_suction, 20, available_pipes)
        discharge_pipe = Piping.find_best_pipe('discharge', mass_flow_rate, density_discharge, 15, available_pipes)

        velocity_discharge = Piping.calculate_velocity(mass_flow_rate, discharge_pipe.inner_diameter,density_discharge)
        pressure_drop_discharge = Piping.calculate_pressure_drop(pipe_length, T_discharge,discharge_pipe.inner_diameter, velocity_discharge, pressure_discharge, density_discharge, refrigerant)

        velocity_suction = Piping.calculate_velocity(mass_flow_rate, suction_pipe.inner_diameter,density_suction)
        pressure_drop_suction = Piping.calculate_pressure_drop(pipe_length, T_evap,suction_pipe.inner_diameter, velocity_suction,pressure_suction, density_suction, refrigerant)

        return velocity_suction, pressure_drop_suction, suction_pipe, discharge_pipe, velocity_discharge, pressure_drop_discharge


    @staticmethod
    def get_allowed_sizes(connection_size, standard_sizes):
        """
        Get the allowed pipe sizes for a given connection size, which include
        the same size and the next smaller size.
        """
        if connection_size in standard_sizes:
            index = standard_sizes.index(connection_size)
        else:
            return []  # If the size is not found in the list, return an empty list

        allowed_sizes = [connection_size]
        if index > 0:
            allowed_sizes.append(standard_sizes[index - 1])

        return allowed_sizes

    def __str__(self):
        return f"{self.get_pipe_type_display()}: {self.name} ({self.inner_diameter} mm)"



class Receiver(models.Model):
    ORIENTATION_CHOICES = [
        ('vertical', 'Vertical'),
        ('horizontal', 'Horizontal'),
    ]
    receiver_name = models.CharField(max_length=100)
    manufacturer = models.CharField(max_length=50)
    receiver_maxpressure = models.FloatField()  # Max high pressure in bar
    receiver_volume = models.FloatField()
    receiver_conn_in = models.FloatField()  # Connection discharge
    receiver_conn_out = models.FloatField()  # Connection suction
    receiver_refrigerant = models.CharField(max_length=50, help_text="Type of refrigerant the receiver is compatible with")
    receiver_orientation = models.CharField(max_length=10,choices=ORIENTATION_CHOICES,)  # Use the defined choices variabledefault='vertical',  # Default valuehelp_text="Orientation of the receiver: Vertical or Horizontal"

    def __str__(self):
        return self.name

class CheckValve(models.Model):
    checkvalve_name = models.CharField(max_length=20)
    checkvalve_model = models.CharField(max_length=20)
    manufacturer = models.CharField(max_length=20)
    checkvalve_conn = models.CharField(max_length=20)
    checkvalve_pressure = models.FloatField()
    checkvalve_kv = models.FloatField()
    checkvalve_mintemperature = models.FloatField()
    checkvalve_maxtemperature = models.FloatField()

    def __str__(self):
        return f"{self.checkvalve_name} ({self.checkvalve_model})"

class SightGlass(models.Model):
    sightglass_model = models.CharField(max_length=20)
    manufacturer = models.CharField(max_length=20)
    sightglass_conn = models.FloatField()
    sightglass_pressure = models.FloatField()
    sightglass_refrigerants = models.JSONField()  # List of refrigerants

    def __str__(self):
        return f"{self.sightglass_model} ({self.sightglass_manufacturer})"

class SuctionAccumulator(models.Model):
    accumulator_model = models.CharField(max_length=20)
    manufacturer = models.CharField(max_length=20)
    accumulator_conn = models.FloatField()
    accumulator_pressuremin = models.FloatField()
    accumulator_pressuremax = models.FloatField()
    accumulator_tempmin = models.FloatField()
    accumulator_tempmax = models.FloatField()
    accumulator_refrigerants = models.JSONField()  # List of refrigerants

    def __str__(self):
        return f"{self.accumulator_model} ({self.accumulator_manufacturer})"


class OilSeparator(models.Model):
    oil_separator_model = models.CharField(max_length=20)
    manufacturer = models.CharField(max_length=20)
    oil_separator_conn = models.FloatField()
    oil_separator_conn_oil = models.FloatField()
    accumulator_pressure_max = models.FloatField()
    accumulator_temp_min = models.FloatField()
    accumulator_temp_max = models.FloatField()
    accumulator_discharge = models.FloatField()  # m3/h
    accumulator_refrigerants = models.JSONField()  # List of refrigerants

    def __str__(self):
        return f"{self.oil_separator_model} ({self.manufacturer})"

class OilSeparatorReceiver(models.Model):
    oil_separator_receiver_model = models.CharField(max_length=20)
    manufacturer = models.CharField(max_length=20)
    oil_separator_receiver_conn = models.FloatField()
    oil_separator_receiver_conn_oil = models.FloatField()
    oil_separator_receiver_pressure_max = models.FloatField()
    oil_separator_receiver_temp_min = models.FloatField()
    oil_separator_receiver_temp_max = models.FloatField()
    oil_separator_receiver_volume = models.FloatField()
    oil_separator_receiver_discharge = models.FloatField()  # m3/h
    oil_separator_receiver_refrigerants = models.JSONField()  # List of refrigerants

    def __str__(self):
        return f"{self.oil_separator_receiver_model} ({self.manufacturer})"

class OilReceiver(models.Model):
    oil_receiver_model = models.CharField(max_length=20)
    manufacturer = models.CharField(max_length=20)
    oil_receiver_conn = models.FloatField()
    oil_receiver_conn_oil = models.FloatField()
    oil_receiver_pressure_max = models.FloatField()
    oil_receiver_temp_min = models.FloatField()
    oil_receiver_temp_max = models.FloatField()
    oil_receiver_volume = models.FloatField()
    oil_receiver_refrigerants = models.JSONField()  # List of refrigerants

    def __str__(self):
        return f"{self.oil_receiver_model} ({self.manufacturer})"













class ExpansionValve(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class SolenoidValve(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

# Refrigerant dictionaries
refrigerants = {
    'HCFCs': {
        'R22': 'HCFC-22'
    },
    'HFCs': {
        'R23': 'HFC-23', 'R32': 'HFC-32', 'R125': 'HFC-125', 'R134a': 'HFC-134a', 'R152a': 'HFC-152a',
        'R227ea': 'HFC-227ea', 'R236fa': 'HFC-236fa', 'R245fa': 'HFC-245fa', 'R404A': 'R404A',
        'R407A': 'R407A', 'R407B': 'R407B', 'R407C': 'R407C', 'R407F': 'R407F', 'R407H': 'R407H',
        'R410A': 'R410A', 'R417A': 'R417A', 'R422A': 'R422A', 'R422D': 'R422D', 'R427A': 'R427A',
        'R438A': 'R438A', 'R442A': 'R442A', 'R448A': 'R448A', 'R449A': 'R449A', 'R449B': 'R449B',
        'R450A': 'R450A', 'R452A': 'R452A', 'R452B': 'R452B', 'R452C': 'R452C', 'R454A': 'R454A',
        'R454B': 'R454B', 'R454C': 'R454C', 'R455A': 'R455A', 'R463A': 'R463A', 'R469A': 'R469A',
        'R471A': 'R471A'
    },
    'HFOs': {
        'R1234yf': 'HFO-1234yf', 'R1234ze': 'HFO-1234ze'
    },
    'HCs': {
        'R290': 'Propane', 'R600a': 'Isobutane', 'R1270': 'Propylene', 'R600': 'Butane', 'R601': 'Butane'
    },
    'Inorganics': {
        'R717': 'Ammonia', 'R718': 'Water'
    },
    'CO2': {
        'R744': 'CarbonDioxide'
    },
    'Blends': {
        'R502': 'R502', 'R503': 'R503', 'R507A': 'R507A', 'R508B': 'R508B', 'R513A': 'R513A',
        'R513B': 'R513B', 'R515B': 'R515B', 'R516A': 'R516A'
    },
    'Other': {
        'R1150': 'Ethylene', 'R1233zd': 'HFO-1233zd', 'R1336mzz': 'HFO-1336mzz'
    }
}