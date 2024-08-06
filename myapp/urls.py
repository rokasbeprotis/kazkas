
from django.urls import path
from .views import input, part_list, select_component

urlpatterns = [
    path('', input, name='input'),  # Set the root URL to the input view
    path('part_list/', part_list, name='part_list'),
    path('select_component/', select_component, name='select_component'),
]