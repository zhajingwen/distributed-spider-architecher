# class Volume24hCex:
#     """
#     补充24H cex 交易量
#     """
#
#     def num_transform(self, num):
#         """
#         数值转换成K M B
#         """
#         # 有可能是None
#         if not num:
#             return num
#         # 10亿 转换成xxB
#         if num > 1000000000:
#             num = round((num/1000000000),2)
#             num = f'{num}B'
#         else:
#             # 100w  转换成xxM
#             if num > 1000000:
#                 num = round((num/1000000), 2)
#                 num = f'{num}M'
#             else:
#                 # 转换成xxK
#                 if num > 1000:
#                     num = round((num / 1000), 2)
#                     num = f'{num}K'
#                 else:
#                     num = int(num)
#         return num
#
#     def add_cex_volume24h(self, data):
#         """
#         增加信息维度 volume24h cex
#         """
#         volume24h_dex = data['volume24h_dex']
#         volume24h_total = data['volume24h_total']
#         # 如果没上线cex，该值为None
#         if volume24h_total:
#             volume24h_cex = volume24h_total - volume24h_dex
#             volume24h_cex = self.num_transform(volume24h_cex)
#         else:
#             volume24h_cex = None
#         # 格式化volume
#         data['volume24h_dex'] = self.num_transform(volume24h_dex)
#         if volume24h_total:
#             data['volume24h_total'] = self.num_transform(volume24h_total)
#         # 组合cex volume
#         data['volume24h_cex'] = volume24h_cex
#         # 如果该值为空表示没有上线任何中心化的交易所，那么totalvolume就是dex的volume
#         if not volume24h_total:
#             data['volume24h_total'] = data['volume24h_dex']
#         return data
#
