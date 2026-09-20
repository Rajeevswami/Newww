from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from app.ai.provider import structured, Question, Evaluation, Scorecard
from app.core.config import settings


class InterviewState(TypedDict, total=False):
    resume_context: dict
    job_context: dict
    conversation_history: list
    topics_covered: list
    question_count: int
    answer: str
    evaluation: dict
    scorecard: dict
    evaluations: list
    complete: bool


async def evaluate_answer(state):
    if settings.openai_api_key:
        evaluation = await structured(
            "Evaluate this answer for relevance, specificity and technical depth; request a follow-up if vague.",
            {
                "job": state["job_context"],
                "question": state["conversation_history"][-1]["content"],
                "answer": state["answer"],
            },
            Evaluation,
        )
    else:
        count = len(state["answer"].split())
        evaluation = {
            "score": min(90, 30 + count),
            "feedback": "Demo feedback: add a concrete example, explain your choices, and quantify the outcome."
            if count < 45
            else "Demo feedback: your answer includes useful detail. Connect the outcome to the requirements of the role.",
            "follow_up": count < 30,
        }
    return {
        "evaluation": evaluation,
        "evaluations": state.get("evaluations", []) + [evaluation],
        "conversation_history": state["conversation_history"]
        + [{"role": "user", "content": state["answer"], "evaluation": evaluation}],
        "answer": "",
    }


async def ask_question(state):
    n = state.get("question_count", 0)
    skills = state["job_context"]["required_skills"] or ["problem solving"]
    topic = skills[min(n, len(skills) - 1)]
    if settings.openai_api_key:
        result = await structured(
            "Ask exactly one concise adaptive interview question. Use resume gaps and the previous evaluation. Five questions maximum; avoid repeating questions.",
            state,
            Question,
        )
        question, topic = result["question"], result["topic"]
    elif n == 0:
        question = f"Let's start with your experience. Tell me about a project that best demonstrates your fit for the {state['job_context']['title']} role. What was your specific contribution?"
    elif state.get("evaluation", {}).get("follow_up"):
        question = f"Let's dig a little deeper. Can you give a specific example involving {topic}, explain the trade-offs you considered, and tell me how you measured success?"
    else:
        question = [
            f"How would you approach a challenging {topic} problem when requirements are unclear?",
            f"Tell me about a time you used {topic} to improve a product. What changed because of your work?",
            f"How do you validate your decisions when working with {topic}? Walk me through your process.",
            "Describe a disagreement with a teammate about a technical or design decision. How did you reach a resolution?",
            "Looking back at your experience, what would you do differently on your next project, and why?",
        ][n]
    return {
        "question_count": n + 1,
        "topics_covered": state.get("topics_covered", []) + [topic],
        "conversation_history": state.get("conversation_history", [])
        + [{"role": "assistant", "content": question}],
        "complete": False,
    }


def route_next(state):
    return "generate_scorecard" if state.get("question_count", 0) >= 5 else "ask_question"


async def generate_scorecard(state):
    if settings.openai_api_key:
        scorecard = await structured(
            "Create an evidence-based coaching scorecard. Recommendation must call for human review, not an automatic hiring decision.",
            state,
            Scorecard,
        )
    else:
        score = round(sum(e["score"] for e in state["evaluations"]) / len(state["evaluations"]))
        scorecard = {
            "overall_score": score,
            "strengths": [
                "Completed the full practice interview",
                "Engaged with role-specific questions",
            ],
            "weaknesses": [
                "Use measurable outcomes and concrete examples",
                "Explain the alternatives you considered",
            ],
            "recommendation": "Practice again, then request human review",
            "summary": "This is a demo coaching report based on answer length, not a validated assessment of ability. Enable OpenAI for contextual feedback.",
        }
    scorecard["mode"] = "OpenAI" if settings.openai_api_key else "Demo"
    return {"scorecard": scorecard, "complete": True}


graph = StateGraph(InterviewState)
graph.add_node("evaluate_answer", evaluate_answer)
graph.add_node("ask_question", ask_question)
graph.add_node("generate_scorecard", generate_scorecard)
graph.add_conditional_edges(
    START, lambda state: "evaluate_answer" if state.get("answer") else "ask_question"
)
graph.add_conditional_edges("evaluate_answer", route_next)
graph.add_edge("ask_question", END)
graph.add_edge("generate_scorecard", END)
interview_graph = graph.compile()
