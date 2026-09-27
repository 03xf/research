"""Minimal Chinese flame-only review page backed by the existing review protocol."""
import argparse
from http.server import ThreadingHTTPServer
from pathlib import Path

import recovery_v1_review_server as base
from recovery_v1_prepare import check_label


class FlameReview(base.Review):
    def save(self, value):
        # Reject smoke and any other class even if a user edits the hidden raw field.
        check_label(value.get('label_text', '').strip(), 1)
        return super().save(value)


class FlameHandler(base.Handler):
    review = None


HTML = base.HTML
HTML = HTML.replace('DJI 标签复核', 'B4 明火框复核')
HTML = HTML.replace('<select id="filter"><option value="priority">优先复核</option><option value="all">全部</option><option value="train">训练</option><option value="validation">开发验证</option><option value="pending">待裁决</option></select>', '<select id="filter"><option value="all">全部 40 张</option><option value="pending">只看未保存</option></select>')
HTML = HTML.replace("cls===0?'#1df0d3':'#ffca35'", "'#ffca35'")
HTML = HTML.replace("(item.sensor==='V'?['smoke','flame']:['hotspot'])", "['火焰']")
HTML = HTML.replace('<h2>画框</h2>', '<h2>请框出图中所有可见火焰</h2>')
HTML = HTML.replace('<label>类别 <select id="category"></select></label>', '<select id="category" hidden></select>')
HTML = HTML.replace('<textarea id="labels" spellcheck="false"></textarea>', '<textarea id="labels" spellcheck="false" style="display:none"></textarea>')
HTML = HTML.replace('选择类别后在图上拖拽画框。保存时，有框自动记为目标样本；空框自动记为无目标。', '在图上拖拽框出全部可见火焰；没有可见火焰就不画框，直接点“保存并下一张”。已有黄框可保留，错误的框可用撤销按钮移除。')
HTML = HTML.replace('<h2>来源</h2>', '<h2>B4 训练图像</h2>')
HTML = HTML.replace('<h2>保存</h2>', '<h2>完成本张</h2>')
HTML = HTML.replace('保存只写入新的复核文件，不修改历史标签。', '保存后自动跳到下一张；不会修改原数据集。')
HTML = HTML.replace("async function save(){", "async function save(){")
HTML = HTML.replace("setStatus('已保存到服务器',true)}catch(error){setStatus('保存失败：'+error.message)}}", "setStatus('已保存到服务器',true);return true}catch(error){setStatus('保存失败：'+error.message);return false}}")
HTML = HTML.replace("async function saveNext(){await save();if(!dirty&&index<keys.length-1)await load(index+1)}", "async function saveNext(){if(await save()&&index<keys.length-1)await load(index+1)}")
HTML = HTML.replace("item.proposed_patch?'已有单框补丁（仅供参考，必须检查全图其他目标）：'+item.proposed_patch:''", "''")
base.HTML = HTML


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--port', type=int, default=8796)
    args = ap.parse_args()
    FlameHandler.review = FlameReview(args.root)
    if len(FlameHandler.review.ledger) != 40:
        raise ValueError('expected exactly 40 review images')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), FlameHandler)
    print(f'B4 flame review: http://127.0.0.1:{args.port}/; images=40', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
