"""The project's KANLinear is numerically the Kolmogorov-Arnold layer of the reference
implementation (pykan, Liu et al. 2024): learnable cubic B-spline functions on every edge plus a
SiLU base term, summed at each output node.

Given pykan's coefficients (coef, scale_base, scale_sp, mask) on the same grid, our layer must
return the same outputs. Skipped if pykan is not installed.
"""

from __future__ import annotations

import unittest

try:
    import torch
    from kan.KANLayer import KANLayer

    HAVE_KAN = True
except Exception:  # noqa: BLE001
    HAVE_KAN = False


@unittest.skipUnless(HAVE_KAN, "pykan not installed")
class KANEquivalence(unittest.TestCase):
    def test_matches_pykan_layer(self):
        from joint_interception.rl.option_policy import KAN_HI, KAN_LO, KANLinear

        torch.manual_seed(0)
        in_f, out_f, grid, k = 5, 3, 8, 3
        ref = KANLayer(in_dim=in_f, out_dim=out_f, num=grid, k=k, grid_range=[KAN_LO, KAN_HI])
        with torch.no_grad():
            ref.coef.copy_(torch.randn_like(ref.coef))
            ref.scale_base.copy_(torch.randn_like(ref.scale_base))
            ref.scale_sp.copy_(torch.rand_like(ref.scale_sp) + 0.5)
        ours = KANLinear(in_f, out_f, grid=grid, order=k)
        with torch.no_grad():
            self.assertTrue(torch.allclose(ours.grid, ref.grid, atol=1e-6))
            m = ref.mask
            ours.spline.copy_((ref.coef * (ref.scale_sp * m)[:, :, None]).permute(1, 0, 2))
            ours.base.weight.copy_((ref.scale_base * m).T)
            ours.base.bias.zero_()
            x = torch.rand(256, in_f) * (KAN_HI - KAN_LO - 1e-3) + KAN_LO
            y_ref = ref(x)[0]
            y_ours = ours(x)
        self.assertTrue(torch.allclose(y_ours, y_ref, atol=1e-5), (y_ours - y_ref).abs().max())


if __name__ == "__main__":
    unittest.main()
