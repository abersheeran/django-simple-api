from django.db import models
from django.core.exceptions import FieldDoesNotExist
from typing import List


def serialize_model(self: models.Model, excludes: List[str] = None) -> dict:
    """
    模型序列化，会根据 select_related 和 prefetch_related 关联查询的结果进行序列化，可以在查询时使用 only、defer 来筛选序列化的字段。
    它不会自做主张的去查询数据库，只用你查询出来的结果，成功避免了 N+1 查询问题。

    # See：
    https://aber.sh/articles/A-new-idea-of-serializing-Django-model/
    """
    excludes = excludes or []
    serialized = set()

    def _serialize_model(model) -> dict:

        # 当 model 存在一对一字段时，会陷入循环，使用闭包的自由变量存储已序列化的 model，
        # 在第二次循环到该 model 时直接返回 model.pk，不再循环。
        nonlocal serialized
        if model in serialized:
            return model.pk
        else:
            serialized.add(model)

        # 当 model 存在一对一或一对多字段，且该字段的值为 None 时，直接返回空{}，否则会报错。
        if model is None:
            return {}

        result = {
            name: _serialize_model(foreign_key)
            for name, foreign_key in model.__dict__["_state"]
            .__dict__.get("fields_cache", {})
            .items()
        }

        # 不可暴露的字段
        buried_fields = getattr(model, "buried_fields", [])
        for name, value in model.__dict__.items():
            if name in buried_fields:
                continue
            try:
                model._meta.get_field(name)
            except FieldDoesNotExist:
                # 非模型字段
                continue
            else:
                result[name] = value

        for name, queryset in model.__dict__.get(
            "_prefetched_objects_cache", {}
        ).items():
            result[name] = serialize_queryset(queryset, excludes)  # type: ignore

        return result

    results = _serialize_model(self)

    # 剔除排斥的字段
    for field in excludes:
        del results[field]

    return results


def serialize_queryset(self: models.QuerySet, excludes: List[str] = None) -> List[dict]:
    return [serialize_model(model, excludes) for model in self]