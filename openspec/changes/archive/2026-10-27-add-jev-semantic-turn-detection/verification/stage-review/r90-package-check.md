# r90增量包独立只读核验（2026-10-26）

- r90归档SHA-256：`3a2d985e5e8edb1cc15aa6a1d39d0e19c66cc1699ddf1274e3e66d7aca0a04c7`，独立实算匹配。
- snapshot所列95文件逐项从归档重读并计算hash，全部匹配；3个生产前端和3个新测试/fixture与当前工作区一致，增量清单无src/后端文件。
- r89基包SHA-256独立实算匹配`b15cf0ac6b6bd7a5faca0e575447b8d9a88615a5577c2d282375e4e854f33e8a`。r90为该基包上的增量输入，不是替代全源包。
- 本次仅包核验，不运行行为测试，不修改冻结输入/既有报告或重打包；本文在包外。
- 核验不改变repair-review-r90的限定结论：全Change仍INSUFFICIENT EVIDENCE，不签完整C、全Change PASS或User Gate2。
