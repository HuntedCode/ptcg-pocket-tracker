from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import UserCollection, Card, UserWant

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
        
class CollectionForm(forms.ModelForm):
    card = forms.ModelChoiceField(queryset=Card.objects.all().order_by('card_set__tcg_id', 'tcg_id'), widget=forms.Select(attrs={'class': 'form-control'}))

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

    def clean(self):
        cleaned_data = super().clean()
        card = cleaned_data.get('card')
        for_trade = cleaned_data.get('for_trade')
        if for_trade and card and not card.is_tradeable:
            raise forms.ValidationError({'for_trade': 'This card is not tradeable based on current game rules.'})
        return cleaned_data

class WantsForm(forms.ModelForm):
    class Meta:
        model = UserWant
        fields = ['card', 'desired_quantity']
        widgets = {
            'desired_quantity': forms.NumberInput(attrs={'min': 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['card'].queryset = Card.objects.all().order_by('card_set__tcg_id', 'tcg_id')