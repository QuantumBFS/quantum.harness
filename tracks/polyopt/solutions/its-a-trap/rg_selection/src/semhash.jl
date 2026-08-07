# semhash.jl — canonical semantic hash of an RGExt extension. Shared by the
# a200 runner (R4c) and release_gates.jl (R4b) so cross-checks compare the
# exact same serialization.
#   include_words=true  : full hash (newwords + blocks) — auto-mode identity
#   include_words=false : block-level hash (gramblocks/zblocks/ycoef only) —
#                         pool-vs-auto identity (vspace words excluded)
using SHA

function ext_semhash(ext; include_words::Bool = true)
    io = IOBuffer()
    if include_words
        for w in sort(ext.newwords); println(io, Int.(w)) end
    end
    for g in ext.gramblocks
        println(io, "G", g.dim)
        for e in sort([(e[2], e[3], string(e[1]), round(e[4], sigdigits = 12)) for e in g.entries])
            println(io, e)
        end
    end
    for z in ext.zblocks; println(io, "Z", z.dim, ":", length(z.entries)) end
    println(io, "Y", length(ext.ycoef))
    return bytes2hex(sha256(take!(io)))
end
