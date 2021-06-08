from typing import Any

from django.conf import settings
from django.db.models import Model
from rest_framework import serializers, fields, relations
from rest_framework.serializers import ModelSerializer

from auther.models import Domain, Role, User, Perm
from auther.utils import generate_password, hash_password
from fancy.serializers import FancySerializer


class BasicDomainSerializer(ModelSerializer):
    class Meta:
        model = Domain
        exclude = []


class BasicPermSerializer(ModelSerializer):
    class Meta:
        model = Perm
        exclude = []


class BasicRoleSerializer(ModelSerializer):
    class Meta:
        model = Role
        exclude = ['perms']


class BasicUserSerializer(ModelSerializer):
    class Meta:
        model = User
        exclude = ['password']


class DomainSerializer(FancySerializer):
    name = fields.CharField(min_length=1, max_length=99)
    address = fields.CharField(min_length=4, max_length=99)
    users_ids = relations.PrimaryKeyRelatedField(source='users', many=True, queryset=User.objects.all(), required=False)
    users = BasicUserSerializer(many=True, required=False)

    class Meta:
        model = Domain
        exclude = []


class PermSerializer(FancySerializer):
    name = fields.CharField(min_length=3, max_length=9, allow_blank=True)
    regex = fields.CharField(min_length=1, max_length=64)
    roles_ids = relations.PrimaryKeyRelatedField(source='roles', many=True, queryset=Role.objects.all(), required=False)
    roles = BasicRoleSerializer(many=True, required=False)

    class Meta:
        model = Perm
        exclude = []


class RoleSerializer(FancySerializer):
    name = fields.CharField(min_length=3, max_length=64)
    users_ids = relations.PrimaryKeyRelatedField(source='users', many=True, queryset=User.objects.all(), required=False)
    users = BasicUserSerializer(many=True, required=False)
    perms_ids = relations.PrimaryKeyRelatedField(source='perms', many=True, queryset=Perm.objects.all(), required=False)
    perms = BasicPermSerializer(many=True, required=False)

    class Meta:
        model = Role
        exclude = []


class UserSerializer(FancySerializer):
    name = fields.CharField(min_length=3, max_length=64, required=False, allow_blank=True)
    username = fields.CharField(min_length=6, max_length=64)
    password = fields.CharField(min_length=8, max_length=64, write_only=True, required=False)
    avatar_token = fields.CharField(min_length=64, max_length=128, required=False)
    active = fields.BooleanField(allow_null=True, default=True, required=False)
    expire = fields.DateTimeField(allow_null=True, required=False)
    domain_id = relations.PrimaryKeyRelatedField(source='domain', queryset=Domain.objects.all(), required=False)
    domain = BasicDomainSerializer(required=False)
    role_id = relations.PrimaryKeyRelatedField(source='role', queryset=Role.objects.all(), required=False)
    role = BasicRoleSerializer(required=False)

    class Meta:
        model = User
        exclude = []

    @staticmethod
    def _hash_password_field(validated_data: dict):
        if 'password' in validated_data:
            validated_data['password'] = hash_password(password=validated_data['password'].encode('utf-8'))
            validated_data['password'] = str(validated_data['password'], 'utf-8')

    def create(self, validated_data: dict) -> Any:
        random_password = None

        # If there is a password field we will hash it
        self._hash_password_field(validated_data)

        # Create a role with same name as model and add it to user
        default_role = settings.AUTHER.get('DEFAULT_ROLE')
        if default_role and 'role_id' not in self.initial_data and 'role' not in self.initial_data:
            role_name = self.Meta.model.__name__.lower()
            role, _ = Role.objects.get_or_create(name=role_name)
            self.validated_data['role_id'] = role.id

        # If password is not provided we generate a random one
        if 'password' not in self.initial_data:
            random_password = generate_password(8)
            hashed_password = str(hash_password(random_password), encoding='ascii')
            self.validated_data['password'] = hashed_password

        # Store record into database
        user = super(UserSerializer, self).create(validated_data)

        # Disable write only option for random passwords
        if random_password:
            self.fields['password'].write_only = False
            user.password = str(random_password, encoding='ascii')

        return user

    def update(self, instance: Model, validated_data: dict) -> Any:
        # If there is a password field we will hash it
        self._hash_password_field(validated_data)

        return super(UserSerializer, self).update(instance=instance, validated_data=validated_data)


# noinspection PyAbstractClass
class LoginSerializer(serializers.Serializer):
    username = fields.CharField(min_length=4, max_length=64)
    password = fields.CharField(min_length=6, max_length=64, write_only=True)


class SessionSerializer(FancySerializer):
    token = fields.CharField(required=True, min_length=64, max_length=64)
    user = UserSerializer(required=True)
    user_agent = fields.CharField(required=True, min_length=200)
    inserted_at = fields.DateTimeField(read_only=True)
