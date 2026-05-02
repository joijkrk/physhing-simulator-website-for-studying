document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("quizForm");
    const result = document.getElementById("quizResult");

    if (!form || !result) {
        return;
    }

    form.addEventListener("submit", async function (event) {
        event.preventDefault();

        const formData = new FormData();
        const first = form.querySelector("input[name='answer_1']:checked");
        const second = form.querySelector("input[name='answer_2']:checked");
        if (!first || !second) {
            result.style.display = "block";
            result.style.borderLeftColor = "#e74c3c";
            result.style.background = "#fdecea";
            result.textContent = "Ответьте на все вопросы перед проверкой.";
            return;
        }
        formData.append("answers", first.value);
        formData.append("answers", second.value);
        const response = await fetch("/quiz/check", {
            method: "POST",
            body: formData,
        });
        const data = await response.json();

        result.style.display = "block";
        if (data.passed) {
            result.style.borderLeftColor = "#27ae60";
            result.style.background = "#edf9ef";
            result.textContent = "Отлично! Вы прошли проверку и правильно распознали фишинг.";
        } else {
            result.style.borderLeftColor = "#e67e22";
            result.style.background = "#fff6e8";
            result.textContent = "Есть ошибки. Перечитайте признаки фишинга и попробуйте снова.";
        }
    });
});
