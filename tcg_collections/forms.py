from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Profile, Message, Booster, Card

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

class ProfileForm(forms.ModelForm):
    display_favorites = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
        initial=''
    )
    class Meta:
        model = Profile
        fields = ['is_trading_active', 'bio', 'favorite_set', 'display_favorites']
        widgets = {
            'is_trading_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'bio': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'favorite_set': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance:
            fav_cards = Card.objects.filter(
                usercollection__user=self.instance.user,
                usercollection__is_favorite=True,
                usercollection__quantity__gt=0
            ).distinct().order_by('name')
            self.fields['display_favorites'].initial = ','.join(map(str, self.instance.display_favorites))
        
    def clean_display_favorites(self):
        value = self.cleaned_data.get('display_favorites', '')
        if value:
            try:
                selected = [int(id_str.strip()) for id_str in value.split(',') if id_str.strip()]
            except ValueError:
                raise forms.ValidationError('Invalid favorite IDs.')
        else:
            selected = []
        if len(selected) > 10:
            raise forms.ValidationError('Max 10 favorites.')
        return selected
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        selected_str = self.cleaned_data['display_favorites']
        instance.display_favorites = [int(s) for s in selected_str]
        if commit:
            instance.save(update_fields=['display_favorites'])
        return instance
        
class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['content']
        widgets = {'content': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'})}

class PackOpenerForm(forms.Form):
    booster = forms.ModelChoiceField(queryset=Booster.objects.all().order_by('name'), label="Select Booster")