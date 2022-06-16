import frappe

from engage.utils import require_login


NOT_FOUND_TEMPLATE = "www/404.html"


@require_login
def get_context(context):
    try:
        year = frappe.form_dict["year"]
        slug = frappe.form_dict["slug"]
    except KeyError:
        context.template = NOT_FOUND_TEMPLATE
        return

    username = frappe.form_dict.get("p")

    t = get_training(year, slug)
    if not (t and t.has_user_as_trainer(frappe.session.user)):
        context.template = NOT_FOUND_TEMPLATE
        return

    latest_submissions = frappe.get_list(
        "Practice Problem Latest Submission",
        filters={"training": t.name},
        fields=["name", "author", "problem", "code", "latest_submission"],
        page_length=10000,
    )
    solved_by_user = {}
    for sub in latest_submissions:
        solved_by_user.setdefault(sub["author"], {})
        solved_by_user[sub["author"]][sub["problem"]] = sub

    participants = t.participants
    for (i, p) in enumerate(participants):
        p.full_name = frappe.get_cached_doc("User", p.user).full_name
        p.num_solved = len(solved_by_user.get(p.user, {}))
        p.active = (p.user == username)

        if p.active:
            context.prev_participant = participants[i - 1] if i >= 1 else None
            context.next_participant = participants[i + 1] if i < (
                len(participants) - 1) else None

    participants.sort(key=lambda p: p.num_solved, reverse=True)

    trainers = t.trainers
    for trainer in trainers:
        trainer.full_name = frappe.get_cached_doc("User",
                                                  trainer.user).full_name

    problem_sets = [
        frappe.get_cached_doc("Problem Set", row.problem_set)
        for row in t.problem_sets
    ]

    for pset in problem_sets:
        pset.problems = [
            frappe.get_doc("Practice Problem", p.problem)
            for p in pset.problems
        ]

        for problem in pset.problems:
            if username:
                submission = solved_by_user.get(username,
                                                {}).get(problem.name, {})
                problem.code = submission.get("code")
                problem.latest_submission_review = frappe.render_template(
                    "frappe/templates/discussions/discussions_section.html", {
                        "doctype": "Practice Problem Latest Submission",
                        "docname": submission["name"],
                        "title": "Review Comments",
                        "cta_title": "New Comment",
                        "single_thread": True,
                    }) if "name" in submission else ""
            else:
                problem.code = get_starter_code(problem)
                problem.latest_submission_review = ""

    first_participant = participants and participants[0] or None
    first_problem = problem_sets and problem_sets[0] and problem_sets[
        0].problems and problem_sets[0].problems[0].name or None

    context.t = t
    context.title = t.title
    context.client = frappe.get_doc("Client", t.client)
    context.participants = participants
    context.trainers = trainers
    context.num_participants = len(participants)
    context.problem_sets = problem_sets
    context.get_participant_review_link = lambda p: p and f"/trainings/{t.name}/review?p={p.user}"
    context.get_participant_full_name = lambda p, limit: p and truncate(p.full_name, limit) or ""
    context.first_participant = first_participant
    context.first_problem = first_problem


def get_training(year, slug):
    tname = f"{year}/{slug}"
    try:
        return frappe.get_doc("Training", tname)
    except frappe.exceptions.DoesNotExistError:
        return


def get_children(child_doctype, parent_name, parent_doctype=None, fields="*"):
    filters = {"parent": parent_name}
    if parent_doctype:
        filters.update({"parenttype": parent_doctype})

    return frappe.get_all(child_doctype, filters=filters, fields=fields)


def get_latest_submission(author, training, problem_set, problem):
    doc_list = frappe.get_list(
        "Practice Problem Latest Submission",
        filters={
            "author": author,
            "training": training,
            "problem_set": problem_set,
            "problem": problem,
        },
        fields="*",
        page_length=1,
    )

    latest = doc_list and doc_list[0] or None
    return latest


def get_starter_code(problem):
    return problem.code_files[0].content


def truncate(text, limit):
    if len(text) > limit:
        return text[:limit-3] + "..."
    return text
