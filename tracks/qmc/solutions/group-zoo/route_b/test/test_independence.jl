@test RouteBWorm.SCHEMA_VERSION == 1
@test realpath(pkgdir(RouteBWorm)) == realpath(joinpath(@__DIR__, ".."))

loaded_names = Set(pkgid.name for pkgid in keys(Base.loaded_modules))
@test "Challenge148" ∉ loaded_names
