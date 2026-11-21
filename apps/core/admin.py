"""Central Django admin configuration for all OmniCore application models."""

from django.apps import apps
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm


SENSITIVE_FIELD_NAMES = {
    'password',
    'code_hash',
    'mfa_secret',
    'token',
    'secret',
    'client_secret',
}


class OmniCoreModelAdmin(admin.ModelAdmin):
    """Useful defaults for browsing, filtering, and editing business records."""

    list_per_page = 50
    show_full_result_count = False
    list_select_related = True

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        all_objects = getattr(self.model, 'all_objects', None)
        return all_objects.all() if all_objects is not None else queryset


class OmniCoreUserCreationForm(UserCreationForm):
    class Meta:
        model = get_user_model()
        fields = ('email', 'first_name', 'last_name')


class OmniCoreUserChangeForm(UserChangeForm):
    class Meta:
        model = get_user_model()
        fields = '__all__'


class OmniCoreUserAdmin(UserAdmin):
    """Keep Django's password management while exposing OmniCore account fields."""

    add_form = OmniCoreUserCreationForm
    form = OmniCoreUserChangeForm
    list_display = (
        'email', 'first_name', 'last_name', 'phone', 'platform_role',
        'is_platform_admin', 'is_staff', 'is_active',
    )
    list_filter = ('platform_role', 'is_platform_admin', 'is_staff', 'is_active', 'is_mfa_enabled')
    search_fields = ('email', 'first_name', 'last_name', 'phone')
    ordering = ('email',)
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'phone', 'avatar')}),
        ('OmniCore access', {'fields': ('is_platform_admin', 'platform_role', 'is_mfa_enabled')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'password1', 'password2'),
        }),
    )


def _model_admin_attributes(model):
    fields = [field for field in model._meta.concrete_fields if not field.many_to_many]
    by_name = {field.name: field for field in fields}
    preferred_names = (
        'tenant', 'company_name', 'name', 'title', 'code', 'email', 'number',
        'registration_number', 'status', 'is_active', 'is_deleted',
        'created_at', 'timestamp', 'updated_at',
    )

    list_display = ['__str__']
    for name in preferred_names:
        field = by_name.get(name)
        if field and name not in SENSITIVE_FIELD_NAMES and name not in list_display:
            list_display.append(name)
        if len(list_display) >= 7:
            break

    list_filter = []
    for field in fields:
        internal_type = field.get_internal_type()
        is_filterable = (
            field.choices
            or internal_type in {'BooleanField', 'NullBooleanField', 'DateField', 'DateTimeField'}
            or (field.is_relation and field.many_to_one)
        )
        if is_filterable and field.name not in SENSITIVE_FIELD_NAMES:
            list_filter.append(field.name)
        if len(list_filter) == 5:
            break

    search_fields = []
    for field in fields:
        if field.name in SENSITIVE_FIELD_NAMES:
            continue
        if field.get_internal_type() in {'CharField', 'TextField', 'EmailField', 'SlugField', 'URLField'}:
            search_fields.append(field.name)
        if len(search_fields) == 8:
            break

    readonly_fields = [
        field.name for field in fields
        if not field.editable or field.name in SENSITIVE_FIELD_NAMES
    ]
    attributes = {
        'list_display': tuple(list_display),
        'list_filter': tuple(list_filter),
        'search_fields': tuple(search_fields),
        'readonly_fields': tuple(readonly_fields),
    }
    if 'created_at' in by_name:
        attributes['date_hierarchy'] = 'created_at'
    elif 'timestamp' in by_name:
        attributes['date_hierarchy'] = 'timestamp'
    return attributes


def register_omnicore_models():
    """Register every concrete model declared by the OmniCore apps."""
    user_model = get_user_model()

    # Django's auth admin may already register a custom AbstractUser with the
    # stock configuration. Replace it with the email-first OmniCore admin.
    if user_model in admin.site._registry:
        admin.site.unregister(user_model)
    admin.site.register(user_model, OmniCoreUserAdmin)

    for model in apps.get_models():
        if not model.__module__.startswith('apps.') or model._meta.proxy:
            continue
        if model in admin.site._registry:
            continue

        if model is user_model:
            continue
        elif model._meta.label == 'audit.AuditLog':
            attributes = _model_admin_attributes(model)
            attributes.update({
                'readonly_fields': tuple(field.name for field in model._meta.concrete_fields),
                'has_add_permission': lambda self, request: False,
                'has_change_permission': lambda self, request, obj=None: False,
                'has_delete_permission': lambda self, request, obj=None: False,
            })
            audit_admin = type(f'{model.__name__}Admin', (OmniCoreModelAdmin,), attributes)
            admin.site.register(model, audit_admin)
        else:
            model_admin = type(
                f'{model.__name__}Admin',
                (OmniCoreModelAdmin,),
                _model_admin_attributes(model),
            )
            admin.site.register(model, model_admin)


register_omnicore_models()
