from django.contrib import admin
from .models import CheckValve, Piping, Compressor, Receiver, SightGlass, SuctionAccumulator, OilSeparator, OilReceiver, OilSeparatorReceiver
from django import forms


class CompressorForm(forms.ModelForm):
    class Meta:
        model = Compressor
        fields = '__all__'
        widgets = {
            'working_field_points': forms.Textarea(attrs={'rows': 4}),
            'additional_constraints': forms.Textarea(attrs={'rows': 4}),
            'refrigerants': forms.Textarea(attrs={'rows': 2}),
        }

@admin.register(Compressor)
class CompressorAdmin(admin.ModelAdmin):
    form = CompressorForm
    list_display = ('name', 'displacement_50Hz', 'displacement_60Hz', 'max_pressure_hp', 'max_pressure_lp')
    search_fields = ('name', 'refrigerants')
    list_filter = ('refrigerants',)  # Allows filtering by refrigerants if needed

@admin.register(Piping)
class PipingAdmin(admin.ModelAdmin):
    list_display = ('name', 'inner_diameter', 'outer_diameter', 'material', 'pipe_type')
    search_fields = ('name', 'material', 'pipe_type')

@admin.register(Receiver)
class ReceiverAdmin(admin.ModelAdmin):
    list_display = ('receiver_name', 'manufacturer', 'receiver_maxpressure', 'receiver_volume', 'receiver_conn_in', 'receiver_conn_out', 'receiver_refrigerant', 'receiver_orientation')
    search_fields = ('receiver_name', 'manufacturer', 'receiver_refrigerant')
    list_filter = ('receiver_orientation', 'manufacturer')
    ordering = ('receiver_name',)

@admin.register(CheckValve)
class CheckValveAdmin(admin.ModelAdmin):
    list_display = ('checkvalve_name', 'checkvalve_model', 'manufacturer', 'checkvalve_conn', 'checkvalve_pressure', 'checkvalve_kv', 'checkvalve_mintemperature', 'checkvalve_maxtemperature')
    search_fields = ('checkvalve_name', 'checkvalve_model', 'manufacturer')
    list_filter = ('manufacturer',)
    ordering = ('checkvalve_name',)

class SightGlassAdmin(admin.ModelAdmin):
    list_display = ('sightglass_model', 'manufacturer', 'sightglass_conn', 'sightglass_pressure')
    search_fields = ('sightglass_model', 'manufacturer')
    list_filter = ('sightglass_model',)
    ordering = ('sightglass_model',)

@admin.register(SuctionAccumulator)
class SuctionAccumulatorAdmin(admin.ModelAdmin):
    list_display = ('accumulator_model', 'manufacturer', 'accumulator_conn', 'accumulator_pressuremin', 'accumulator_pressuremax', 'accumulator_tempmin', 'accumulator_tempmax')
    search_fields = ('accumulator_model', 'manufacturer')
    list_filter = ('accumulator_model',)
    ordering = ('accumulator_model',)

@admin.register(OilSeparator)
class OilSeparatorAdmin(admin.ModelAdmin):
    list_display = ('oil_separator_model', 'manufacturer', 'oil_separator_conn', 'oil_separator_conn_oil', 'accumulator_pressure_max', 'accumulator_temp_min', 'accumulator_temp_max', 'accumulator_discharge', 'accumulator_refrigerants')
    search_fields = ('oil_separator_model', 'manufacturer')
    list_filter = ('manufacturer',)
    ordering = ('oil_separator_model',)

@admin.register(OilSeparatorReceiver)
class OilSeparatorReceiverAdmin(admin.ModelAdmin):
    list_display = ('oil_separator_receiver_model', 'manufacturer', 'oil_separator_receiver_conn', 'oil_separator_receiver_conn_oil', 'oil_separator_receiver_pressure_max', 'oil_separator_receiver_temp_min', 'oil_separator_receiver_temp_max', 'oil_separator_receiver_volume', 'oil_separator_receiver_discharge', 'oil_separator_receiver_refrigerants')
    search_fields = ('oil_separator_receiver_model', 'manufacturer')
    list_filter = ('manufacturer',)
    ordering = ('oil_separator_receiver_model',)

@admin.register(OilReceiver)
class OilReceiverAdmin(admin.ModelAdmin):
    list_display = ('oil_receiver_model', 'manufacturer', 'oil_receiver_conn', 'oil_receiver_conn_oil', 'oil_receiver_pressure_max', 'oil_receiver_temp_min', 'oil_receiver_temp_max', 'oil_receiver_volume', 'oil_receiver_refrigerants')
    search_fields = ('oil_receiver_model', 'manufacturer')
    list_filter = ('manufacturer',)
    ordering = ('oil_receiver_model',)
