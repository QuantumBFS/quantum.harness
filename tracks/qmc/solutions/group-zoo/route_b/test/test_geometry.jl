@testset "periodic lattice counts" begin
    cases = (
        (:chain, 6, 6, 2, 6),
        (:square, 4, 16, 4, 32),
        (:honeycomb, 4, 32, 3, 48),
        (:triangle, 4, 16, 6, 48),
    )

    for (name, L, nsites, degree, nbonds) in cases
        lattice = build_lattice(name, L)
        @test lattice.nsites == nsites
        @test length(lattice.bonds) == nbonds
        @test all(length(lattice.incident[site]) == degree for site in 1:nsites)
        @test validate_lattice(lattice)
        @test length(lattice.directed) == 2nbonds

        for bond in 1:nbonds
            forward = lattice.directed[2bond - 1]
            reverse = lattice.directed[2bond]
            @test (forward.src, forward.dst) == (reverse.dst, reverse.src)
            @test reverse_displacement(lattice, forward) == (reverse.du, reverse.dv)
            @test (reverse.du, reverse.dv) == (-forward.du, -forward.dv)
        end
    end
end

@testset "primitive displacements survive periodic wrapping" begin
    honeycomb = build_lattice(:honeycomb, 4)
    honeycomb_wrap = only(filter(
        edge -> edge.src == 1 && edge.dst == 8,
        honeycomb.directed,
    ))
    @test (honeycomb_wrap.du, honeycomb_wrap.dv) == (-1, 0)

    triangle = build_lattice(:triangle, 4)
    triangle_u_wrap = only(filter(
        edge -> edge.src == 4 && edge.dst == 1,
        triangle.directed,
    ))
    @test (triangle_u_wrap.du, triangle_u_wrap.dv) == (1, 0)

    triangle_diagonal_wrap = only(filter(
        edge -> edge.src == 4 && edge.dst == 13,
        triangle.directed,
    ))
    @test (triangle_diagonal_wrap.du, triangle_diagonal_wrap.dv) == (1, -1)
end

@testset "invalid lattice sizes and names are rejected" begin
    @test_throws ArgumentError build_lattice(:chain, 2)
    @test_throws ArgumentError build_lattice(:square, 2)
    @test_throws ArgumentError build_lattice(:triangle, 2)
    @test_throws ArgumentError build_lattice(:honeycomb, 1)
    @test_throws ArgumentError build_lattice(:kagome, 4)
end
