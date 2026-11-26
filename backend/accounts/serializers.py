from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.utils import get_md5_hash_password

from .models import User


def check_password_strength(password, user=None, field="password"):
    """Run Django's password validators and report errors on the given field."""
    try:
        validate_password(password, user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError({field: list(exc.messages)})


def check_email_free(email, exclude_pk=None):
    """Emails are stored in lowercase and must be unique, ignoring case."""
    email = email.strip().lower()
    queryset = User.objects.filter(email__iexact=email)
    if exclude_pk:
        queryset = queryset.exclude(pk=exclude_pk)
    if queryset.exists():
        raise serializers.ValidationError("A user with this email already exists.")
    return email


class UserSerializer(serializers.ModelSerializer):
    """Read-only view of a user."""

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "first_name", "last_name",
            "role", "is_active", "date_joined",
        ]
        read_only_fields = fields


class UserCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["username", "email", "password", "first_name", "last_name", "role"]
        extra_kwargs = {"password": {"write_only": True}}

    def validate_email(self, value):
        return check_email_free(value)

    def validate(self, attrs):
        candidate = User(
            username=attrs.get("username"),
            email=attrs.get("email"),
            first_name=attrs.get("first_name", ""),
            last_name=attrs.get("last_name", ""),
        )
        check_password_strength(attrs["password"], candidate)
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        username = validated_data.pop("username")
        email = validated_data.pop("email")
        return User.objects.create_user(
            username=username, email=email, password=password, **validated_data
        )


class UserUpdateSerializer(serializers.ModelSerializer):
    """Administrator edits: no password here, and no self lock-out."""

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "role", "is_active"]

    def validate_email(self, value):
        return check_email_free(value, exclude_pk=self.instance.pk)

    def validate(self, attrs):
        request = self.context.get("request")
        if request and self.instance == request.user:
            if "role" in attrs and attrs["role"] != self.instance.role:
                raise serializers.ValidationError(
                    {"role": "You cannot change your own role."}
                )
            if attrs.get("is_active") is False:
                raise serializers.ValidationError(
                    {"is_active": "You cannot deactivate your own account."}
                )
        return attrs


class SetPasswordSerializer(serializers.Serializer):
    """Administrator sets a new password for another user."""

    password = serializers.CharField(write_only=True)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("The current password is incorrect.")
        return value

    def validate(self, attrs):
        user = self.context["request"].user
        check_password_strength(attrs["new_password"], user, field="new_password")
        return attrs


class LoginSerializer(TokenObtainPairSerializer):
    """Login with username or email. Also returns the user's data."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"] = user.username
        token["role"] = user.role  # informative only: permissions read the database
        return token

    def validate(self, attrs):
        identifier = attrs.get(self.username_field, "")
        if "@" in identifier:
            user = User.objects.filter(email__iexact=identifier.strip()).first()
            if user:
                attrs[self.username_field] = user.get_username()
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data

        # Explicitly dispatch user_logged_in signal for JWT API login
        from django.contrib.auth.signals import user_logged_in
        request = self.context.get("request")
        user_logged_in.send(sender=self.user.__class__, request=request, user=self.user)

        return data


class AccountTokenRefreshSerializer(TokenRefreshSerializer):
    """Refresh only active-user tokens whose password has not since changed."""

    def validate(self, attrs):
        # TokenRefreshSerializer checks expiry/blacklisting and account activity,
        # but SimpleJWT 5.5.1 does not check its password-revocation claim here.
        token = self.token_class(attrs["refresh"])
        user_id = token.payload.get(api_settings.USER_ID_CLAIM)
        user = User.objects.filter(**{api_settings.USER_ID_FIELD: user_id}).first()
        if user is None or not api_settings.USER_AUTHENTICATION_RULE(user):
            raise AuthenticationFailed("No active account found for this refresh token.")

        if api_settings.CHECK_REVOKE_TOKEN:
            claim = token.get(api_settings.REVOKE_TOKEN_CLAIM)
            if claim != get_md5_hash_password(user.password):
                raise AuthenticationFailed("Refresh token was revoked after a password change.")

        return super().validate(attrs)


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(write_only=True, trim_whitespace=True)

    def validate(self, attrs):
        try:
            token = RefreshToken(attrs["refresh"])
        except TokenError as exc:
            raise serializers.ValidationError({
                "refresh": "Refresh token is invalid, expired, or already revoked."
            }) from exc

        request_user = self.context["request"].user
        token_user_id = token.payload.get(api_settings.USER_ID_CLAIM)
        if str(token_user_id) != str(request_user.pk):
            raise serializers.ValidationError({"refresh": "Refresh token does not belong to this user."})

        if api_settings.CHECK_REVOKE_TOKEN:
            claim = token.get(api_settings.REVOKE_TOKEN_CLAIM)
            if claim != get_md5_hash_password(request_user.password):
                raise serializers.ValidationError({"refresh": "Refresh token has been revoked."})

        attrs["token"] = token
        return attrs
