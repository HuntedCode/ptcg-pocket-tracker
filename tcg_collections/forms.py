from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Card, Profile, Message, Booster

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['is_trading_active', 'bio']
        widgets = {
            'is_trading_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'bio': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['content']
        widgets = {'content': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'})}

class PackOpenerForm(forms.Form):
    booster = forms.ModelChoiceField(queryset=Booster.objects.all().order_by('name'), label="Select Booster")