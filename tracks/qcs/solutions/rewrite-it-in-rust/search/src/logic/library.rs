use crate::GateOp;

pub(super) enum Cell {
    Constant(bool),
    Alias { inverted: bool },
    Gate(GateOp),
}

pub(super) fn cell_by_name(name: &str) -> Option<Cell> {
    match name {
        "ZERO" => Some(Cell::Constant(false)),
        "ONE" => Some(Cell::Constant(true)),
        "INV" => Some(Cell::Alias { inverted: true }),
        "BUF" => Some(Cell::Alias { inverted: false }),
        "AND2" => Some(Cell::Gate(GateOp::And)),
        "OR2" => Some(Cell::Gate(GateOp::Or)),
        "NAND2" => Some(Cell::Gate(GateOp::Nand)),
        "NOR2" => Some(Cell::Gate(GateOp::Nor)),
        "XOR2" => Some(Cell::Gate(GateOp::Xor)),
        "XNOR2" => Some(Cell::Gate(GateOp::Xnor)),
        _ => None,
    }
}
