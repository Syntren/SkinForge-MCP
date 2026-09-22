#!/usr/bin/env python3
"""
SkinForge Example: Build the Syntren Techwear Cyberpunk skin from scratch using the ASCII DSL.
"""

import os
import sys

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from skinforge import (
    SkinCanvas,
    TECHWEAR_CYBERPUNK as P,
    render_3d_turnaround,
    render_composite_2d,
    render_bottom_up,
    SkinValidator
)

def build_syntren():
    canvas = SkinCanvas()

    # ========================================================
    # ==================== LAYER 1 (BASE) ====================
    # ========================================================

    # Face with anime bangs and 2x2 glowing eyes (vivid electric neon purple matched to reference.jpeg)
    P_head_front = {
        "#": [33, 33, 34, 255], "=": [41, 41, 42, 255], "+": [36, 36, 37, 255], "~": [33, 32, 34, 255],
        "*": [35, 34, 36, 255], "o": [37, 36, 38, 255], "x": [39, 38, 40, 255], "s": [38, 38, 39, 255],
        "m": [15, 15, 16, 255], "d": [29, 29, 30, 255], "h": [35, 34, 35, 255], "H": [30, 29, 30, 255],
        "^": [31, 31, 32, 255], "i": [31, 30, 32, 255], "I": [36, 35, 37, 255], "w": [30, 29, 31, 255],
        "W": [32, 32, 33, 255], "b": [39, 39, 41, 255], "B": [41, 40, 42, 255], "p": [39, 38, 39, 255],
        "P": [34, 34, 35, 255], "0": [37, 37, 38, 255], "1": [34, 34, 36, 255], "2": [38, 37, 39, 255],
        "3": [18, 12, 22, 255], "4": [14, 10, 18, 255], "5": [187, 150, 147, 255], "6": [218, 171, 170, 255],
        "7": [14, 10, 18, 255],
        # Eyes: Exact vibrant electric purple & specular highlights sampled from reference.jpeg
        "8": [181, 157, 219, 255],  # Upper left highlight (pale lavender #b59ddb)
        "9": [125, 11, 210, 255],   # Upper left iris shadow (deep vivid violet #7d0bd2)
        "A": [241, 187, 185, 255], "C": [239, 186, 188, 255],
        "D": [121, 11, 208, 255],   # Upper right iris shadow (deep vivid violet #790bd0)
        "E": [175, 145, 220, 255],  # Upper right highlight (pale lavender #af91dc)
        "F": [20, 19, 20, 255], "G": [18, 17, 21, 255],
        "J": [250, 248, 252, 255],  # Lower left specular shine (pure white #faf8fc)
        "K": [175, 54, 248, 255],   # Lower left iris (electric vivid neon purple #af36f8)
        "L": [245, 197, 196, 255], "M": [245, 203, 202, 255],
        "N": [172, 55, 250, 255],   # Lower right iris (electric vivid neon purple #ac37fa)
        "O": [245, 242, 248, 255],  # Lower right specular shine (pure white #f5f2f8)
        "Q": [23, 21, 25, 255], "R": [235, 183, 184, 255], "S": [237, 188, 190, 255], "T": [242, 194, 194, 255],
        "U": [241, 195, 196, 255], "V": [241, 194, 195, 255], "X": [243, 192, 196, 255], "Y": [243, 194, 198, 255],
        "Z": [238, 185, 190, 255]
    }
    canvas.set_ascii("head_front", """
        d#~*h#~H
        ^io==I#w
        W+b=BxpP
        0ss1*ox2
        +34567m+
        m89ACDEF
        GJKLMNOQ
        RSTUVXYZ
    """, P_head_front)

    # Base Head: Inner hood lining on rear & sides, hair crown in front
    P_head_top = {"#": [20, 16, 24, 255], "=": [28, 24, 34, 255], "+": [38, 34, 46, 255], "~": [210, 100, 255, 255], "*": [41, 41, 42, 255], "o": [41, 40, 42, 255], "x": [33, 32, 34, 255], "s": [14, 12, 18, 255], "m": [160, 55, 225, 255], "d": [33, 33, 34, 255], "h": [35, 34, 35, 255], "H": [35, 35, 36, 255], "^": [41, 40, 41, 255], "i": [44, 43, 45, 255], "I": [43, 42, 43, 255], "w": [42, 41, 42, 255], "W": [36, 36, 38, 255], "b": [34, 33, 35, 255], "B": [30, 29, 30, 255], "p": [35, 34, 36, 255], "P": [33, 32, 33, 255], "0": [29, 28, 29, 255]}
    canvas.set_ascii("head_top", """
        s#====#s
        #=#==#=#
        ##=++=##
        #=++++=#
        #m~~~~m#
        H**^iIwW
        db*ooohB
        dxxphxP0
    """, P_head_top)

    canvas.set_ascii("head_back", """
        _#====#_
        #=#++++#
        ##=++++#
        #=++++=#
        #=++++=#
        #=#====#
        ###==###
        _##==##_
    """, P)

    P_head_right = {"#": [20, 16, 24, 255], "=": [28, 24, 34, 255], "+": [80, 18, 120, 255], "~": [160, 55, 225, 255], "*": [14, 12, 18, 255], "o": [39, 39, 40, 255], "x": [39, 38, 40, 255], "s": [38, 34, 46, 255], "m": [210, 100, 255, 255], "d": [44, 43, 45, 255], "h": [43, 42, 44, 255], "H": [34, 33, 34, 255], "^": [36, 36, 37, 255], "i": [46, 46, 47, 255], "I": [44, 44, 45, 255], "w": [36, 35, 37, 255], "W": [47, 46, 48, 255], "b": [47, 45, 48, 255], "B": [37, 36, 38, 255], "p": [233, 192, 196, 255], "P": [234, 191, 195, 255], "0": [33, 31, 34, 255], "1": [226, 184, 188, 255], "2": [231, 183, 188, 255], "3": [34, 31, 35, 255], "4": [31, 29, 30, 255], "5": [236, 178, 183, 255], "6": [239, 183, 186, 255]}
    canvas.set_ascii("head_right", """
        *#==+hoH
        #=#=~ox^
        ##=smiIw
        #==smWdx
        #=#=~bdB
        ##==+pP0
        ####~123
        *###+456
    """, P_head_right)

    P_head_left = {"#": [20, 16, 24, 255], "=": [28, 24, 34, 255], "+": [80, 18, 120, 255], "~": [160, 55, 225, 255], "*": [14, 12, 18, 255], "o": [37, 36, 38, 255], "x": [37, 37, 38, 255], "s": [210, 100, 255, 255], "m": [38, 34, 46, 255], "d": [46, 45, 47, 255], "h": [28, 27, 28, 255], "H": [35, 34, 35, 255], "^": [37, 36, 37, 255], "i": [29, 29, 30, 255], "I": [32, 32, 33, 255], "w": [42, 41, 43, 255], "W": [44, 44, 45, 255], "b": [47, 46, 48, 255], "B": [46, 44, 47, 255], "p": [33, 31, 32, 255], "P": [236, 189, 195, 255], "0": [235, 187, 192, 255], "1": [31, 29, 31, 255], "2": [235, 183, 189, 255], "3": [227, 177, 182, 255], "4": [234, 181, 185, 255], "5": [233, 180, 186, 255], "6": [28, 25, 27, 255]}
    canvas.set_ascii("head_left", """
        hH^+==#*
        iox~=#=#
        IwWsm=##
        xdbsm==#
        odB~=#=#
        pP0+==##
        123~####
        456+###*
    """, P_head_left)

    canvas.set_ascii("head_bottom", """
    _#====#_
    #======#
    ##dddd##
    #ddmmdd#
    dmmsssmd
    mssmmsms
    ssssssss
    ssssssss
""", P)

    # Torso: Hoodie with drawstrings, collar, and Kangaroo pocket
    canvas.set_ascii("body_front", """
        _#mssm#_
        #=B##B=#
        ##L==L##
        =#B##B=#
        #=M==D=#
        ##M#####
        =#D==##=
        #=####=#
        =_++++_=
        #======#
        ##====##
        __====__
    """, P)

    # Torso Back Base: Clean dark hoodie fabric (purple oval ring removed)
    P_body_back = {"#": [20, 16, 24, 255], "=": [14, 12, 18, 255], "+": [28, 24, 34, 255], "~": [15, 13, 19, 255], "*": [38, 34, 46, 255]}
    canvas.set_ascii("body_back", """
        =#++++#=
        #+****+#
        #####=##
        #=~~~~=#
        ###=#=##
        ######=#
        ##=##=##
        #=#~#=##
        ###=#=##
        ######=#
        #++++++#
        =#++++==
    """, P_body_back)

    canvas.set_ascii("body_right", """
        _#=#
        #=#=
        ##=#
        =#=#
        #=##
        ##=#
        #==#
        _##_
    """, P)

    canvas.set_ascii("body_left", """
        _#=#
        #=#=
        ##=#
        =#=#
        #=##
        ##=#
        #==#
        _##_
    """, P)

    canvas.fill_part("body_top", P["#"])
    canvas.fill_part("body_bottom", P["_"])

    # Arms Base: Sleeves with skin hands at bottom (forearm purple mark removed)
    P_right_arm_right = {"#": [20, 16, 24, 255], "=": [28, 24, 34, 255], "+": [224, 177, 180, 255], "~": [14, 12, 18, 255], "*": [212, 163, 172, 255], "o": [210, 100, 255, 255], "x": [245, 185, 255, 255], "s": [80, 18, 120, 255], "m": [160, 55, 225, 255]}
    canvas.set_ascii("right_arm_right", """
        ~##~
        #ox#
        #sm#
        #==#
        ##=#
        ~==~
        #==#
        #=##
        #==#
        *++*
        ++*+
        ++++
    """, P_right_arm_right)
    canvas.set_ascii("right_arm_front", """
        #==#
        #++#
        ##=#
        =#=#
        #==#
        ##=#
        _==_
        #==#
        _==_
        smms
        ssss
        mssm
    """, P)
    canvas.set_ascii("right_arm_back", """
        #==#
        #==#
        ##+#
        #_=#
        #==#
        ##=#
        _==_
        #==#
        _==_
        dmmd
        smms
        ssss
    """, P)
    canvas.set_ascii("right_arm_left", """
        _##_
        #==#
        ##=#
        #==#
        _##_
        #==#
        _==_
        #==#
        _==_
        dmmd
        smmd
        smms
    """, P)
    canvas.fill_part("right_arm_top", P["#"])
    canvas.fill_part("right_arm_bottom", P["s"])

    # Mirror right arm to left arm
    canvas.mirror_limb("right_arm", "left_arm", mirror_layer2=False)

    # Legs Base: Cargo pants + purple techwear sneakers with white sole & laces
    canvas.set_ascii("right_leg_front", """
        1210
        0121
        1110
        0221
        1110
        0010
        0110
        1001
        uBBu
        uwwu
        gwwg
        gwwg
    """, P)
    canvas.set_ascii("right_leg_back", """
        0121
        1110
        0221
        1110
        0111
        0010
        0110
        1001
        uBBu
        ubbu
        uggu
        gwwg
    """, P)
    canvas.set_ascii("right_leg_right", """
        1210
        1121
        0221
        1110
        1110
        0010
        0110
        1001
        uBBu
        ubbu
        gwwg
        gwwg
    """, P)
    canvas.set_ascii("right_leg_left", """
        0110
        0110
        0110
        0110
        0110
        0000
        0110
        1001
        uBBu
        ubbu
        uggu
        gwwg
    """, P)
    canvas.fill_part("right_leg_top", P["1"])
    canvas.set_ascii("right_leg_bottom", """
        gwwg
        wwww
        wwww
        gwwg
    """, P)

    # Left Leg Base: includes subtle metallic silver chain line on pants
    canvas.set_ascii("left_leg_front", """
        0C21
        12k0
        011x
        1220
        0111
        0100
        0110
        1001
        uBBu
        uwwu
        gwwg
        gwwg
    """, P)
    canvas.set_ascii("left_leg_back", """
        1210
        0111
        1220
        0111
        1110
        0100
        0110
        1001
        uBBu
        ubbu
        uggu
        gwwg
    """, P)
    canvas.set_ascii("left_leg_left", """
        01kx
        1211
        1220
        0111
        0111
        0100
        0110
        1001
        uBBu
        ubbu
        gwwg
        gwwg
    """, P)
    canvas.set_ascii("left_leg_right", """
        0110
        0110
        0110
        0110
        0110
        0000
        0110
        1001
        uBBu
        ubbu
        uggu
        gwwg
    """, P)
    canvas.fill_part("left_leg_top", P["1"])
    canvas.set_ascii("left_leg_bottom", """
        gwwg
        wwww
        wwww
        gwwg
    """, P)


    # ========================================================
    # ==================== LAYER 2 (OUTER) ===================
    # ========================================================

    # Hat: Hood on rear half, 3D hair crown & bangs clusters in front
    P_hat_top = {".": [0, 0, 0, 0], "#": [20, 16, 24, 255], "=": [28, 24, 34, 255], "+": [32, 28, 36, 255], "~": [22, 20, 26, 255], "*": [38, 34, 46, 255], "o": [210, 100, 255, 255], "x": [14, 12, 18, 255], "s": [160, 55, 225, 255], "m": [31, 30, 31, 255], "d": [36, 35, 36, 255], "h": [35, 34, 35, 255], "H": [34, 33, 33, 255]}
    canvas.set_ascii("hat_top", """
        x#====#x
        #=#==#=#
        ##=**=##
        #=****=#
        #soooos#
        ~++~~++~
        +~+~~+~+
        .+mdhH+.
    """, P_hat_top)

    canvas.set_ascii("hat_back", """
        _#====#_
        #=#++++#
        ##=++++#
        #=++++=#
        #=++++=#
        #=#====#
        ###==###
        _##==##_
    """, P)

    P_hat_right = {".": [0, 0, 0, 0], "#": [20, 16, 24, 255], "=": [28, 24, 34, 255], "+": [80, 18, 120, 255], "~": [160, 55, 225, 255], "*": [14, 12, 18, 255], "o": [38, 34, 46, 255], "x": [210, 100, 255, 255], "s": [34, 33, 36, 255], "m": [45, 44, 46, 255], "d": [38, 37, 39, 255], "h": [23, 24, 26, 255]}
    canvas.set_ascii("hat_right", """
        *#==+...
        #=#=~...
        ##=ox..s
        #==ox..m
        #=#=~..d
        ##==+..h
        ####~...
        *###+...
    """, P_hat_right)

    P_hat_left = {".": [0, 0, 0, 0], "#": [20, 16, 24, 255], "=": [28, 24, 34, 255], "+": [80, 18, 120, 255], "~": [160, 55, 225, 255], "*": [14, 12, 18, 255], "o": [210, 100, 255, 255], "x": [38, 34, 46, 255], "s": [33, 32, 33, 255], "m": [46, 46, 47, 255], "d": [34, 33, 34, 255], "h": [28, 28, 29, 255]}
    canvas.set_ascii("hat_left", """
        ...+==#*
        ...~=#=#
        s..ox=##
        m..ox==#
        d..~=#=#
        h..+==##
        ...~####
        ...+###*
    """, P_hat_left)

    canvas.set_ascii("hat_bottom", """
        _#====#_
        #======#
        ##====##
        #==..==#
        #=....=#
        ........
        ........
        ........
    """, P)

    # 3D hair bangs clusters; rows 0..4 layered anime bangs, lower rows 5..7 100% transparent!
    P_hat_front = {".": [0, 0, 0, 0], "#": [44, 43, 45, 255], "=": [36, 35, 36, 255], "+": [35, 34, 35, 255], "~": [43, 42, 43, 255], "*": [44, 44, 45, 255], "o": [32, 31, 32, 255], "x": [34, 34, 34, 255], "s": [43, 42, 44, 255], "m": [37, 36, 37, 255], "d": [40, 38, 41, 255], "h": [36, 35, 38, 255], "H": [41, 41, 42, 255], "^": [42, 41, 42, 255], "i": [40, 38, 40, 255], "I": [43, 43, 44, 255], "w": [33, 31, 32, 255], "W": [46, 45, 46, 255], "b": [44, 43, 44, 255], "B": [39, 39, 40, 255], "p": [44, 44, 46, 255], "P": [39, 38, 39, 255], "0": [46, 44, 45, 255], "1": [49, 48, 49, 255], "2": [47, 46, 48, 255], "3": [41, 40, 42, 255], "4": [33, 33, 34, 255]}
    canvas.set_ascii("hat_front", """
        ..o==x..
        .++s~md.
        hH^##iIw
        W*~#bBp*
        P0.12.34
        ........
        ........
        ........
    """, P_hat_front)

    canvas.set_ascii("jacket_top", """
        _#====#_
        ##=++=##
        #======#
        _#====#_
    """, P)

    # 3D Drawstrings, kangaroo pocket flap, and ribbed hem on jacket_front
    canvas.set_ascii("jacket_front", """
        ........
        ..B..B..
        ..L..L..
        ..B..B..
        ..M..D..
        ..M.....
        ..D.....
        ........
        ..++++..
        ........
        ........
        ..====..
    """, P)

    # 3D Glowing Cyber "S" Emblem on jacket_back (Layer 2)
    canvas.set_ascii("jacket_back", """
        _#====#_
        #======#
        ..PBBP..
        .BL..B.L
        .BL.....
        ..PBBP..
        .....BL.
        .B..BL..
        .LPBBP..
        ..DPD...
        #======#
        __====__
    """, P)

    # 3D Oversized Sleeves: Outer cyber badge, vertical stripes & 3D cuffs
    canvas.set_ascii("right_sleeve_right", """
        _##_
        #BL#
        #DP#
        ....
        #==#
        _==_
        #==#
        ====
        _##_
        ....
        ....
        ....
    """, P)
    canvas.set_ascii("right_sleeve_front", """
        ....
        _##_
        #==#
        ##=#
        #==#
        _==_
        #==#
        ====
        _##_
        ....
        ....
        ....
    """, P)
    canvas.set_ascii("right_sleeve_back", """
        ....
        _##_
        #==#
        ##=#
        #==#
        _==_
        #==#
        ====
        _##_
        ....
        ....
        ....
    """, P)
    canvas.set_ascii("right_sleeve_left", """
        ....
        _##_
        #==#
        ##=#
        #==#
        _==_
        #==#
        ====
        _##_
        ....
        ....
        ....
    """, P)
    canvas.fill_part("right_sleeve_top", P["#"])
    canvas.fill_part("right_sleeve_bottom", P["."])

    # Mirror right sleeve to left sleeve
    canvas.mirror_limb("right_arm", "left_arm", mirror_layer2=True)

    # 3D Cargo Pocket Flaps (Layer 2) - Clean, ZERO floating white chain blocks!
    canvas.set_ascii("right_pants_right", """
        ....
        ....
        0330
        0220
        0PP0
        ....
        ....
        ....
    """, P)
    canvas.set_ascii("left_pants_left", """
        ....
        ....
        0330
        0220
        0PP0
        ....
        ....
        ....
    """, P)
    canvas.set_ascii("left_pants_front", """
        ....
        ....
        ....
        ....
        ....
        ....
        ....
        ....
    """, P)

    # Export skin
    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    skin_path = os.path.join(out_dir, "skins", "skin_syntren.png")
    canvas.export_png(skin_path)

    # Copy to root and output for user convenience
    import shutil
    shutil.copy(skin_path, "/mnt/storage/My/Projects/Skin/skin_syntren.png")
    shutil.copy(skin_path, "/mnt/storage/My/Projects/Skin/output/skin_final.png")

    # Render previews
    p3d = os.path.join(out_dir, "previews", "3d_turnaround.png")
    p2d = os.path.join(out_dir, "previews", "2d_composite.png")
    p_bot = os.path.join(out_dir, "previews", "preview_bottom_up.png")
    render_3d_turnaround(skin_path, p3d)
    render_composite_2d(skin_path, p2d)
    render_bottom_up(skin_path, p_bot)

    # Also update root previews
    shutil.copy(p3d, "/mnt/storage/My/Projects/Skin/preview_3d_turnaround.png")
    shutil.copy(p2d, "/mnt/storage/My/Projects/Skin/preview_2d.png")
    shutil.copy(p_bot, "/mnt/storage/My/Projects/Skin/preview_bottom_up.png")

    # Run validator
    validator = SkinValidator(skin_path)
    valid, report = validator.validate()
    print(report)
    print(f"\n[+] Syntren skin built, validated, and rendered successfully to '{skin_path}'!")

if __name__ == "__main__":
    build_syntren()
