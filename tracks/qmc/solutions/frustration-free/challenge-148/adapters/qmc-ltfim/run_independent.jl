#!/usr/bin/env julia

using Challenge148LTFIM

try
    exit(Challenge148LTFIM.main())
catch error
    println(stderr, "QMC_LTFIM adapter failed: ", sprint(showerror, error))
    exit(1)
end
