from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Profile, Message, Booster, Card, UserWant

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

class ProfileForm(forms.ModelForm):
    trade_threshold = forms.ChoiceField(
        choices=Profile.trade_threshold.field.choices,
        widget=forms.Select(attrs={'class': 'select select-accent'}),
        label='Trading Preference'
    )


    display_favorites = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
        initial=''
    )

    ICON_CHOICES = [
        ('abra.png', 'Abra'),
        ('bellsprout.png', 'Bellsprout'),
        ('bulbasaur.png', 'Bulbasaur'),
        ('caterpie.png', 'Caterpie'),
        ('charmander.png', 'Charmander'),
        ('dratini.png', 'Dratini'),
        ('eevee.png', 'Eevee'),
        ('jigglypuff.png', 'Jigglypuff'),
        ('mankey.png', 'Mankey'),
        ('meowth.png', 'Meowth'),
        ('mew.png', 'Mew'),
        ('pidgey.png', 'Pidgey'),
        ('pikachu.png', 'Pikachu'),
        ('pokeball.png', 'Pokeball'),
        ('psyduck.png', 'Psyduck'),
        ('rattata.png', 'Rattata'),
        ('snorlax.png', 'Snorlax'),
        ('squirtle.png', 'Squirtle'),
        ('venonat.png', 'Venonat'),
        ('zubat.png', 'Zubat')
    ]

    COLOR_CHOICES = [
        ('#f0ede3', 'Off White (Colorless)'),
        ('#364855', 'Dark Gray (Darkness)'),
        ('#b79b44', 'Gold (Dragon)'),
        ('#d6549c', 'Pink (Fairy)'),
        ('#e85935', 'Orange (Fighting)'),
        ('#f54334', 'Red (Fire)'),
        ('#00a355', 'Green (Grass)'),
        ('#f3e44c', 'Yellow (Lightning)'),
        ('#9aa1a7', 'Light Gray (Metal)'),
        ('#96539c', 'Purple (Psychic)'),
        ('#0e8cc7', 'Blue (Water)')
    ]

    THEME_CHOICES = [
        ('colorless', 'Off White (Colorless)'),
        ('darkness', 'Dark Gray (Darkness)'),
        ('default', 'Default'),
        ('dragon', 'Gold (Dragon)'),
        ('fairy', 'Pink (Fairy)'),
        ('fighting', 'Orange (Fighting)'),
        ('fire', 'Red (Fire)'),
        ('grass', 'Green (Grass)'),
        ('lightning', 'Yellow (Lightning)'),
        ('metal', 'Light Gray (Metal)'),
        ('psychic', 'Purple (Psychic)'),
        ('water', 'Blue (Water)'),
    ]

    pic_icon = forms.ChoiceField(
        choices=ICON_CHOICES,
        widget=forms.Select(attrs={'class': 'select'}), 
        label='Profile Icon'
    )

    pic_bg_color = forms.ChoiceField(
        choices=COLOR_CHOICES,
        widget=forms.Select(attrs={'class': 'select'}),
        label='Background Color'
    )

    theme = forms.ChoiceField(
        choices=THEME_CHOICES,
        widget=forms.Select(attrs={'class': 'select'}),
        label='Profile Theme'
    )

    class Meta:
        model = Profile
        fields = ['is_trading_active', 'trade_threshold', 'bio', 'favorite_set', 'display_favorites', 'pic_icon', 'pic_bg_color', 'theme']
        widgets = {
            'is_trading_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'bio': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'favorite_set': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance:
            self.fields['trade_threshold'].initial = self.instance.trade_threshold

            fav_cards = Card.objects.filter(
                usercollection__user=self.instance.user,
                usercollection__is_favorite=True,
                usercollection__quantity__gt=0
            ).distinct().order_by('name')
            self.fields['display_favorites'].initial = ','.join(map(str, self.instance.display_favorites))
            
            config = self.instance.pic_config
            self.fields['pic_icon'].initial = config.get('icon', 'pokeball.png')
            self.fields['pic_bg_color'].initial = config.get('bg_color', '#0e8cc7')
            
            self.fields['theme'].initial = self.instance.theme
        
    def clean_display_favorites(self):
        value = self.cleaned_data.get('display_favorites', '')
        value = value.replace('[', '').replace(']', '').replace(' ', '')
        if not value.strip():
            return []
        if value:
            try:
                selected = [int(id_str.strip()) for id_str in value.split(',') if id_str.strip()]
            except ValueError as e:
                print("ValueError: ", e)
        else:
            selected = []
        
        print("Selected:", selected)
        if len(selected) > 10:
            raise forms.ValidationError('Max 10 favorites.')
        return selected
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.trade_threshold = int(self.cleaned_data['trade_threshold'])
        selected_str = self.cleaned_data['display_favorites']
        instance.display_favorites = [int(s) for s in selected_str]
        instance.pic_config = {
            'icon': self.cleaned_data['pic_icon'],
            'bg_color': self.cleaned_data['pic_bg_color']
        }
        print(instance.pic_config)
        if commit:
            instance.save()
        return instance
        
class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['content']
        widgets = {'content': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'})}

class PackOpenerForm(forms.Form):
    booster = forms.ModelChoiceField(queryset=Booster.objects.all().order_by('name'), label="Select Booster")

class TradeWantForm(forms.Form):
    wanted_card = forms.ModelChoiceField(
        queryset=UserWant.objects.none(),
        label='Select a Card from Your Wishlist',
        widget=forms.Select(attrs={'class': 'select select-primary w-full'})
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields['wanted_card'].queryset = UserWant.objects.filter(
                user=user,
                desired_quantity__gt=0
            ).select_related('card').order_by('card__tcg_id')
            