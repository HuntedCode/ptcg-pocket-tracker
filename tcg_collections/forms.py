from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import UserCollection, Card

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
        
class CollectionForm(forms.ModelForm):
    card = forms.ModelChoiceField(queryset=Card.objects.all().order_by('card_set__name', 'name'), widget=forms.Select(attrs={'class': 'form-control'}))

    class Meta:
        model = UserCollection
        fields = ['card', 'quantity', 'for_trade']
        widgets = {
            'quantity': forms.NumberInput(attrs={'min': 0, 'value': 1}),
            'for_trade': forms.CheckboxInput(),
        }

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fields['card'].queryset = Card.objects.all().order_by('card_set__tcg_id', 'tcg_id')
            self.fields['card'].widget.attrs.update({'class': 'form-select'})