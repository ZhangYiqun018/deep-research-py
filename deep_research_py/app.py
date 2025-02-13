import gradio as gr
import asyncio
from typing import List, Dict
from deep_research import deep_research, write_final_report
from feedback import generate_feedback
import os

class ResearchSession:
    """管理研究会话的状态"""
    def __init__(self):
        self.query: str = ""
        self.questions: List[str] = []
        self.answers: List[str] = []
        self.report_language: str = "zh"
        self.breadth: int = 4
        self.depth: int = 2
        
    def set_query(self, query: str):
        self.query = query
        
    def set_questions(self, questions: List[str]):
        self.questions = questions
        
    def set_answers(self, answers: List[str]):
        self.answers = answers
        
    def get_combined_query(self) -> str:
        qa_pairs = zip(self.questions, self.answers)
        qa_text = "\n".join(f"Q: {q}\nA: {a}" for q, a in qa_pairs)
        return f"Initial Query: {self.query}\nFollow-up Questions and Answers:\n{qa_text}"

async def research_handler(session: ResearchSession, progress=gr.Progress()) -> Dict:
    """执行研究流程：调用深度搜索和生成最终报告"""
    progress(0.1, desc="开始研究...")
    research_results = await deep_research(
        query=session.get_combined_query(),
        breadth=session.breadth,
        depth=session.depth,
        concurrency=2
    )
    progress(0.7, desc="生成报告...")
    report = await write_final_report(
        prompt=session.get_combined_query(),
        learnings=research_results["learnings"],
        visited_urls=research_results["visited_urls"],
        report_language=session.report_language
    )
    progress(1.0, desc="完成!")
    return {
        "title": report["title"],
        "report": report["final_report"],
        "learnings": research_results["learnings"],
        "sources": research_results["visited_urls"]
    }

# 全局会话对象（注意：多用户场景下需更严格的状态管理）
session = ResearchSession()

async def on_get_questions_fixed(query_text: str, use_search_enhancement: bool = True):
    """
    根据用户输入的研究主题生成跟进问题
    Args:
        query_text: 研究主题
        use_search_enhancement: 是否使用搜索增强
    更新会话中的问题列表，并返回：
      - 问题展示的 Markdown 内容
      - 对于最多 10 个答案输入框的更新信息
    """
    session.set_query(query_text)
    questions = await generate_feedback(query=query_text, use_search_enhancement=use_search_enhancement)
    session.set_questions(questions)
    if questions:
        md = "### 跟进问题:\n" + "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
    else:
        md = "未生成跟进问题。"
    # 针对最多 10 个答案输入框：显示与问题数量对应的框，其余隐藏
    updates = []
    for i in range(10):
        if i < len(questions):
            updates.append(gr.update(visible=True, label=f"回答 {i+1}（问题：{questions[i]}）"))
        else:
            updates.append(gr.update(visible=False))
    return [md] + updates

async def on_start_research_async(*args):
    """
    收集答案以及参数输入（最后 3 个为：lang, breadth, depth），更新会话状态，
    然后调用研究流程，返回研究结果（标题、报告、研究发现、参考来源）。
    """
    # 根据输入参数数量计算：前面所有为答案
    answers = list(args[:-3])
    lang = args[-3]
    breadth = args[-2]
    depth = args[-1]
    valid_answers = [a for a in answers if a and a.strip() != ""]
    session.set_answers(valid_answers)
    session.report_language = lang
    session.breadth = breadth
    session.depth = depth
    results = await research_handler(session)
    notice = "<h2 style='color: green; text-align: center;'>报告生成完毕！</h2>"
    return [results["title"], results["report"], results["learnings"], results["sources"], notice]

def create_ui():
    with gr.Blocks(
        title="Deep Research Assistant",
        theme=gr.themes.Soft(
            primary_hue="blue",
            secondary_hue="indigo",
        ),
    ) as app:
        gr.Markdown(
            """
            # 🔍 Deep Research Assistant
            
            <div style="text-align: center; margin: 20px 0;">
                <h3>AI驱动的智能研究助手</h3>
                <p style="color: #666;">让AI助你深入探索任何研究主题</p>
            </div>
            
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 10px; margin: 10px 0;">
                <h4>📝 使用步骤：</h4>
                <ol>
                    <li>输入您感兴趣的研究主题</li>
                    <li>获取AI生成的跟进问题</li>
                    <li>回答相关问题以明确研究方向</li>
                    <li>设置研究参数</li>
                    <li>开始深度研究并生成报告</li>
                </ol>
            </div>
            """
        )
        
        with gr.Row():
            # 左侧主要操作区域
            with gr.Column(scale=7):
                with gr.Group():
                    gr.Markdown("### 📌 研究主题")
                    query = gr.Textbox(
                        label="请描述您的研究主题",
                        placeholder="例如：deep research...",
                        lines=3
                    )
                    with gr.Row():
                        get_questions_btn = gr.Button(
                            "获取跟进问题",
                            variant="primary",
                            scale=2
                        )
                        use_search = gr.Checkbox(
                            label="启用搜索增强",
                            value=True,
                            info="利用实时搜索结果提升问题质量",
                            scale=1
                        )
                
                with gr.Group():
                    gr.Markdown("### 🤔 跟进问题")
                    questions_md = gr.Markdown(
                        "点击上方「获取跟进问题」按钮生成问题",
                        elem_classes="question-display"
                    )
                    
                    # 使用统一的样式包装答案输入框
                    with gr.Group():
                        answer_boxes = [
                            gr.Textbox(
                                label=f"回答 {i+1}",
                                visible=False,
                                lines=2,
                                elem_classes="answer-box"
                            ) for i in range(10)
                        ]
            
            # 右侧参数设置区域
            with gr.Column(scale=3):
                with gr.Group():
                    gr.Markdown("### ⚙️ 研究参数")
                    with gr.Group():
                        language = gr.Radio(
                            choices=["zh", "en"],
                            value="zh",
                            label="报告语言",
                            info="选择最终报告的语言(报告语言偶尔还是会不稳定，最终版换成DeepSeek-R1应该会好)"
                        )
                        breadth = gr.Slider(
                            minimum=2,
                            maximum=10,
                            value=4,
                            step=1,
                            label="研究广度",
                            info="更大的值会带来更多样的研究视角"
                        )
                        depth = gr.Slider(
                            minimum=1,
                            maximum=5,
                            value=2,
                            step=1,
                            label="研究深度",
                            info="更大的值会带来更深入的分析"
                        )
                    
                    with gr.Row():
                        start_btn = gr.Button(
                            "🚀 开始研究",
                            variant="primary",
                            size="lg"
                        )
                        download_btn = gr.Button(
                            "💾 下载报告",
                            variant="secondary",
                            size="lg"
                        )

        # 研究结果展示区域
        with gr.Group():
            gr.Markdown("### 📊 研究结果")
            completion_notice = gr.Markdown(
                value="",
                elem_classes="notice"
            )
            
            with gr.Accordion("📑 研究报告", open=False):
                title_out = gr.Textbox(
                    label="报告标题",
                    elem_classes="report-title"
                )
                report_out = gr.Markdown(
                    label="研究报告",
                    elem_classes="report-content"
                )
            
            with gr.Row():
                with gr.Column():
                    learnings_out = gr.JSON(
                        label="🔍 研究发现",
                        elem_classes="findings"
                    )
                with gr.Column():
                    sources_out = gr.JSON(
                        label="📚 参考来源",
                        elem_classes="sources"
                    )

        # 添加自定义CSS
        gr.Markdown("""
            <style>
            .question-display {
                background: #f8f9fa;
                padding: 15px;
                border-radius: 8px;
                margin: 10px 0;
            }
            .answer-box {
                border: 1px solid #e0e0e0;
                margin: 8px 0;
            }
            .notice {
                text-align: center;
                padding: 10px;
                margin: 10px 0;
            }
            .report-title {
                font-size: 1.2em;
                font-weight: bold;
            }
            .findings, .sources {
                height: 300px;
                overflow-y: auto;
            }
            </style>
        """)

        # 事件绑定保持不变
        get_questions_btn.click(
            fn=on_get_questions_fixed,
            inputs=[query, use_search],
            outputs=[questions_md] + answer_boxes
        )
        
        start_btn.click(
            fn=on_start_research_async,
            inputs=answer_boxes + [language, breadth, depth],
            outputs=[title_out, report_out, learnings_out, sources_out, completion_notice]
        )
        
        download_btn.click(
            fn=lambda report: report,
            inputs=[report_out],
            outputs=[],
            js="""
            (report) => {
                const blob = new Blob([report], {type: 'text/markdown'});
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'research_report.md';
                a.click();
            }
            """
        )

    return app

if __name__ == "__main__":
    app = create_ui()
    app.launch(share=True) 