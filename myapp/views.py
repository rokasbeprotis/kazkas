from django.shortcuts import render
from django.http import JsonResponse
import json
from .models import CheckValve, Compressor, ExpansionValve, SolenoidValve, Piping, Receiver, OilSeparator, OilSeparatorReceiver, OilReceiver, SuctionAccumulator, SightGlass


standard_pipe_sizes = [12, 16, 18, 22, 28, 35, 42, 54, 64, 76]  # etc.

def part_list(request):
    # Retrieve parameters from GET request
    compressors = int(request.GET.get('compressors', 1))
    circuits = int(request.GET.get('circuits', 1))
    q_capacity = float(request.GET.get('q_capacity', 0))/circuits
    T_evap = float(request.GET.get('tevap', 0))  # Evaporator temperature
    T_cond = float(request.GET.get('tcond', 0))  # Condenser temperature
    subcooling = float(request.GET.get('subcooling', 0))
    superheat = float(request.GET.get('superheat', 0))
    refrigerant = request.GET.get('refrigerant', 'R134a')
    frequency = float(request.GET.get('frequency', 50))

    # Handle added components
    added_components = []
    line_type = request.GET.get('line_type')
    component_type = request.GET.get('component_type')
    parallel_count = int(request.GET.get('parallel_count', 1))

    if line_type and component_type:
        added_components.append({
            'line_type': line_type,
            'component_type': component_type,
            'parallel_count': parallel_count
        })

    # Retrieve all compressors
    compressors = Compressor.objects.all()
    oil_separators_receivers = OilSeparatorReceiver.objects.all()
    oil_separators = OilSeparator.objects.all()
    oil_receivers = OilReceiver.objects.all()
    suction_accumulators = SuctionAccumulator.objects.all()
    sight_glass = SightGlass.objects.all()
    check_valve = CheckValve.objects.all()
    receiver = Receiver.objects.all()



    # Calculate best compressor
    # Initialize variables
    min_difference = float('inf')
    closest_q_compressor = None
    best_compressor = None
    compressors_with_q = []

    # Iterate over compressors to find the best one
    for compressor in compressors:
         if refrigerant in compressor.refrigerants:
            try:
                q_compressor = compressor.calculate_q_compressor(frequency, refrigerant, T_evap, T_cond, subcooling, superheat)[0]

                if q_compressor is None:
                    continue

                difference = abs(q_capacity - q_compressor)
                if difference < min_difference:
                    min_difference = difference
                    closest_q_compressor = q_compressor
                    best_compressor = compressor

                compressors_with_q.append({
                    'id': compressor.id,
                    'name': compressor.name,
                    'q_compressor': q_compressor
                })
            except Exception as e:
                print(f"Error calculating q_compressor for compressor {compressor.id}: {e}")


    # Retrieve available pipes
    available_pipes = Piping.objects.all()
    suction_pipes_list = []
    discharge_pipes_list = []
    suction_pipes = Piping.objects.filter(pipe_type='suction')
    discharge_pipes = Piping.objects.filter(pipe_type='discharge')


    if best_compressor:

        # Determine allowed sizes for discharge and suction connections
        allowed_discharge_sizes = Piping.get_allowed_sizes(best_compressor.discharge_conn, standard_pipe_sizes)
        allowed_suction_sizes = Piping.get_allowed_sizes(best_compressor.suction_conn, standard_pipe_sizes)
        print(f"allowed discharge {allowed_discharge_sizes}")
        print(f"allowed suction {allowed_suction_sizes}")

        # Filter available pipes for discharge based on allowed discharge sizes
        filtered_discharge_pipes = [pipe for pipe in available_pipes if pipe.outer_diameter in allowed_discharge_sizes]

        # Filter available pipes for suction based on allowed suction sizes
        filtered_suction_pipes = [pipe for pipe in available_pipes if pipe.outer_diameter in allowed_suction_sizes]

        mass_flow_rate = best_compressor.calculate_q_compressor(frequency, refrigerant, T_evap, T_cond, subcooling, superheat)[2]

        T_discharge = best_compressor.calculate_q_compressor(frequency, refrigerant, T_evap, T_cond, subcooling, superheat
            )[1]


        # Get best pipe for discharge
        _, _, _, discharge_pipe, velocity_discharge, pressure_drop_discharge = Piping.get_best_pipes(
            refrigerant, T_evap, T_discharge,mass_flow_rate, 10, filtered_discharge_pipes, T_cond, superheat, subcooling)

        # Get best pipe for suction
        velocity_suction, pressure_drop_suction, suction_pipe, _, _, _ = Piping.get_best_pipes(
             refrigerant, T_evap, T_discharge, mass_flow_rate, 10, filtered_suction_pipes, T_cond, superheat, subcooling)


        print(f"Discharge Pipe: {discharge_pipe}")
        # print(f"Suction Pipe: {suction_pipe}")
        print(f"discharge velocity, pressure{velocity_discharge, pressure_drop_discharge}")
        # print(f"suction velocity, pressure{velocity_suction, pressure_drop_suction}")
    else:
        suction_pipe = None
        discharge_pipe = None

    for pipe in suction_pipes:
        try:
            velocity_suction, pressure_drop_suction, _, _ = pipe.pipe_parameters(refrigerant, T_evap, T_discharge, mass_flow_rate, 10, T_cond, superheat,subcooling, pipe.inner_diameter)
            if pipe is None:
                continue

            suction_pipes_list.append({
                'id': pipe.id,
                'name': pipe.name,
                'velocity_suction': velocity_suction,
                'pressure_drop_suction': pressure_drop_suction,
                'inner_diameter': pipe.inner_diameter,
                'outer_diameter': pipe.outer_diameter,
                'material': pipe.material
            })

        except Exception as e:
            print(f"Error calculating pipe {pipe.id}: {e}")

    for pipe in discharge_pipes:
        try:
            _, _, velocity_discharge, pressure_drop_discharge = pipe.pipe_parameters(refrigerant, T_evap, T_discharge, mass_flow_rate, 10, T_cond, superheat,subcooling, pipe.inner_diameter)
            if pipe is None:
                continue

            discharge_pipes_list.append({
                'id': pipe.id,
                'name': pipe.name,
                'velocity_discharge': velocity_discharge,
                'pressure_drop_discharge': pressure_drop_discharge,
                'inner_diameter': pipe.inner_diameter,
                'outer_diameter': pipe.outer_diameter,
                'material': pipe.material
            })

        except Exception as e:
            print(f"Error calculating pipe {pipe.id}: {e}")


    # Retrieve all components for selection
    check_valves = CheckValve.objects.all()
    expansion_valves = ExpansionValve.objects.all()
    solenoid_valves = SolenoidValve.objects.all()
    receivers = Receiver.objects.all()

    # Prepare context
    context = {
        'discharge_pipes_list': discharge_pipes_list,
        'suction_pipes_list': suction_pipes_list,
        'discharge_pipes': discharge_pipes,
        'velocity_discharge': velocity_discharge,
        'pressure_drop_discharge': pressure_drop_discharge/100000,
        'velocity_suction': velocity_suction,
        'pressure_drop_suction': pressure_drop_suction/100000,
        'check_valves': check_valves,
        'expansion_valves': expansion_valves,
        'solenoid_valves': solenoid_valves,
        'receivers': receivers,
        'compressors': compressors_with_q,
        'selected_compressor': best_compressor,
        'closest_q_compressor': closest_q_compressor,
        'suction_pipe': suction_pipe,
        'discharge_pipe': discharge_pipe,
        'oil_separators_receivers': oil_separators_receivers,
        'oil_separators' : oil_separators,
        'oil_receivers': oil_receivers,
        'suction_accumulators': suction_accumulators,
        'sight_glass': sight_glass,
        'check_valve': check_valve,
        'receiver': receiver,
        'selected_check_valve': request.session.get('selected_check_valve', None),
        'selected_expansion_valve': request.session.get('selected_expansion_valve', None),
        'selected_solenoid_valve': request.session.get('selected_solenoid_valve', None),
        'selected_receiver': request.session.get('selected_receiver', None),
        'selected_suction_pipe': request.session.get('selected_suction_pipe', None),
        'selected_discharge_pipe': request.session.get('selected_discharge_pipe', None),
    }

    return render(request, 'part_list.html', context)

def select_component(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            component_type = data.get('type')
            component_id = data.get('id')

            # Store selected component in session
            if component_type == 'check_valve':
                request.session['selected_check_valve'] = component_id
            elif component_type == 'compressor':
                request.session['selected_compressor'] = component_id
            elif component_type == 'expansion_valve':
                request.session['selected_expansion_valve'] = component_id
            elif component_type == 'solenoid_valve':
                request.session['selected_solenoid_valve'] = component_id
            elif component_type == 'receiver':
                request.session['selected_receiver'] = component_id
            elif component_type == 'suction_pipe':
                request.session['selected_suction_pipe'] = component_id
            elif component_type == 'discharge_pipe':
                request.session['selected_discharge_pipe'] = component_id
            else:
                return JsonResponse({'success': False, 'message': 'Invalid component type'})

            return JsonResponse({'success': True})

        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    else:
        return JsonResponse({'success': False, 'message': 'Invalid request method'})

def input(request):
    return render(request, 'input.html')




