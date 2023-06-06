import json
import dataclasses
from typing import Type, Any, Optional
from pydantic import BaseConfig, BaseModel, ValidationError
from pydantic.fields import ModelField, FieldInfo


def create_publish_field(
    name: str,
    type_: Type[Any],
) -> ModelField:
    """
    Create a new publish field. Raises if type_ is invalid.
    """

    try:
        return ModelField(
            name=name,
            type_=type_,
            class_validators={},
            model_config=BaseConfig,
            field_info=FieldInfo()
        )
    except RuntimeError:
        raise Exception(
            "Invalid args for publish field! Hint: "
            f"check that {type_} is a valid Pydantic field type. "
            "If you are using a return type annotation that is not a valid Pydantic "
            "field (e.g. Union[Response, dict, None]) you can disable generating the "
            "publish model from the type annotation with not setting publish_model "
            "in EventPublisher()"
        ) from None


def serialize_payload(
        *,
        field: Optional[ModelField] = None,
        payload_content: Any,
):
    payload_content = _prepare_payload_content(payload_content)
    if not field:
        return _encode(payload_content)

    body, errors = field.validate(payload_content, {}, loc='payload')
    if errors:
        raise ValidationError(errors, field)

    return _encode(body.dict())


def _prepare_payload_content(
    payload: Any,
) -> Any:
    if isinstance(payload, BaseModel):
        read_with_orm_mode = getattr(payload.__config__, "read_with_orm_mode", None)
        if read_with_orm_mode:
            return payload

        return payload.dict(by_alias=True)
    elif isinstance(payload, list):
        return [
            _prepare_payload_content(item)
            for item in payload
        ]

    elif isinstance(payload, dict):
        return {
            k: _prepare_payload_content(v)
            for k, v in payload.items()
        }

    elif dataclasses.is_dataclass(payload):
        return dataclasses.asdict(payload)

    return payload


def _encode(data: Any) -> bytes:
    return json.dumps(data).encode()
