import pandas as pd
from other_spider.dexfilter.file import path

pd.set_option('display.max_colwidth', None)  # 能显示的最大宽度, 否则to_html出来的地址就不全

def gen_html_content():
    """
    构造html信息
    """
    df = pd.read_excel(f'{path}result.xlsx')
    df_html = df.to_html(escape=False)
    head = \
        """
        <head>
            <meta charset="utf-8">
            <STYLE TYPE="text/css" MEDIA=screen>

                table.dataframe {
                    border-collapse: collapse;
                    border: 2px solid #a19da2;
                    /*居中显示整个表格*/
                    margin: auto;
                }

                table.dataframe thead {
                    border: 2px solid #91c6e1;
                    background: #f1f1f1;
                    padding: 10px 10px 10px 10px;
                    color: #333333;
                }

                table.dataframe tbody {
                    border: 2px solid #91c6e1;
                    padding: 10px 10px 10px 10px;
                }

                table.dataframe tr {

                }

                table.dataframe th {
                    vertical-align: top;
                    font-size: 14px;
                    padding: 10px 10px 10px 10px;
                    color: #105de3;
                    font-family: arial;
                    text-align: center;
                }

                table.dataframe td {
                    text-align: center;
                    padding: 10px 10px 10px 10px;
                }

                body {
                    font-family: 宋体;
                }

                h1 {
                    color: #5db446
                }

                div.header h2 {
                    color: #0002e3;
                    font-family: 黑体;
                }
                h3 {
                    font-size: 22px;
                    background-color: rgba(0, 2, 227, 0.71);
                    text-shadow: 2px 2px 1px #de4040;
                    color: rgba(239, 241, 234, 0.99);
                    line-height: 1.5;
                }

                h4 {
                    color: #e10092;
                    font-family: 楷体;
                    font-size: 20px;
                    text-align: center;
                }
            </STYLE>
        </head>
        """

    # 构造模板的附件（100）
    body = f"""
        <body>

        <div align="center" class="header">
            <!--标题部分的信息-->
            <h1 align="center">Hello!&nbsp;请查看当前目标代币的状态</h1>
        </div>

        <hr>

        <div class="content">
            <!--正文内容-->
            <div>
                <h4></h4>
                {df_html}
            </div>
            <hr>
            <p style="color:#FF0000";>您也可以从附件中查看</p>
        </div>
        </body>
        """
    html_msg= "<html>" + head + body + "</html>"
    return html_msg
