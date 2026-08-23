// ==========================================
// WEST WINDSOR BEE STATION - FOCAL FRAME
// 15cm x 15cm Target Ring with 1cm Metric Studs
// ==========================================

$fn = 40; // Curve smoothness

// --- PARAMETERS (in mm) ---
outer_dim = 150;        // 15cm Outer Frame
inner_dim = 100;        // 10cm Viewing Window
frame_thick = 4;        // 4mm sturdy base thickness

// Stud Specs (1cm spacing along top rail)
stud_diam = 3.0;        // 3mm stud diameter
stud_height = 2.0;      // 2mm raised height
stud_spacing = 10.0;    // 10mm (1cm) center-to-center

// Stake Mounting Specs
stake_hole_diam = 6.5;   // Fits standard 1/4 inch (6mm) bamboo stake
mount_block_h = 20;

module base_frame() {
    difference() {
        // Outer Solid Frame
        cube([outer_dim, outer_dim, frame_thick], center=true);
        
        // Inner Viewport Cutout
        cube([inner_dim, inner_dim, frame_thick + 2], center=true);
    }
}

module cm_studs() {
    // Places 10 raised studs spaced 1cm (10mm) apart across the top rail
    // Ranging from -45mm to +45mm along the top edge
    for (i = [-45 : stud_spacing : 45]) {
        translate([i, outer_dim/2 - 12, frame_thick/2])
            cylinder(h=stud_height, d=stud_diam, center=false);
    }
}

module color_calibration_recess() {
    // Corner slot for white/gray color reference card
    translate([outer_dim/2 - 15, outer_dim/2 - 15, frame_thick/2 - 0.5])
        cube([20, 20, 1.2], center=true);
}

module stake_mount() {
    // Bottom clip bracket for garden stake
    translate([0, -outer_dim/2 - mount_block_h/2 + 2, 0]) {
        difference() {
            cube([25, mount_block_h, frame_thick * 2], center=true);
            
            // Hole for bamboo or wooden garden stake
            rotate([90, 0, 0])
                cylinder(h=mount_block_h + 5, d=stake_hole_diam, center=true);
        }
    }
}

// --- FINAL MODEL ASSEMBLY ---
union() {
    difference() {
        union() {
            base_frame();
            stake_mount();
        }
        color_calibration_recess();
    }
    cm_studs(); // Adds the 1cm studs on top of the frame surface
}
