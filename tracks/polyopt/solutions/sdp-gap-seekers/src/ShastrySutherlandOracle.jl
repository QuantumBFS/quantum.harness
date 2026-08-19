module ShastrySutherlandOracle

using ..SquareJ1J2Prototype: Site, PauliWord
using ..GenericGapModel: LocalPatch

export dimer_partner,
       canonical_dimer,
       validate_dimer_covering,
       dimer_product_moment,
       dimer_product_energy_density,
       isolated_dimer_gap,
       singlet_projector_expectation

"""
Partner of a square-lattice site in the standard Shastry-Sutherland
orthogonal-dimer covering.
"""
function dimer_partner(site::Site)
    if iseven(site.x)
        return iseven(site.y) ?
               Site(site.x - 1, site.y + 1) :
               Site(site.x + 1, site.y + 1)
    end
    return iseven(site.y) ?
           Site(site.x - 1, site.y - 1) :
           Site(site.x + 1, site.y - 1)
end

function canonical_dimer(site::Site)
    partner = dimer_partner(site)
    return isless(site, partner) ? (site, partner) : (partner, site)
end

"""
Check involution, diagonal geometry, and one-partner coverage on a finite set
of representative sites. Partners may lie outside the representative set.
"""
function validate_dimer_covering(sites::AbstractVector{Site})
    length(unique(sites)) == length(sites) || return false
    for site in sites
        partner = dimer_partner(site)
        dimer_partner(partner) == site || return false
        abs(partner.x - site.x) == 1 || return false
        abs(partner.y - site.y) == 1 || return false
    end
    return true
end

"""
Exact Pauli-word moment in the infinite product of dimer singlets.

For one singlet, `<sigma_i^a sigma_j^b> = -delta_ab` and every one-site
Pauli moment vanishes. Moments on distinct dimers factorize.
"""
function dimer_product_moment(word::PauliWord, patch::LocalPatch)
    factors_by_dimer =
        Dict{Tuple{Site,Site},Vector{Tuple{Site,UInt8}}}()

    for (site_id, axis) in word.ops
        1 <= site_id <= length(patch.sites) ||
            throw(ArgumentError("Pauli word uses a site outside the patch"))
        site = patch.sites[site_id]
        dimer = canonical_dimer(site)
        push!(
            get!(factors_by_dimer, dimer, Tuple{Site,UInt8}[]),
            (site, axis),
        )
    end

    value = 1
    for factors in values(factors_by_dimer)
        length(factors) == 2 || return 0
        factors[1][1] != factors[2][1] || return 0
        factors[1][2] == factors[2][2] || return 0
        value = -value
    end
    return value
end

"""Exact ground-state energy per site at `g = 0` and dimer coupling one."""
dimer_product_energy_density() = -3//8

"""Exact local triplet excitation gap at `g = 0` and dimer coupling one."""
isolated_dimer_gap() = 1//1

"""`<1/4 I - S_i*S_j>` on any occupied singlet dimer."""
singlet_projector_expectation() = 1//1

end
