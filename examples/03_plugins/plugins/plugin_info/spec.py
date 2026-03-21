from core.extension.spec_builder import SpecBuilder

spec = SpecBuilder("plugin_info") \
    .var("version", "str") \
    .var("author", "str") \
    .build()
