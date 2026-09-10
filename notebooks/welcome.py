import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md(
        """
        # 👋 marimo-desktop

        This notebook is running on the Python interpreter bundled with the app —
        nothing was installed on your system.

        Edit a cell and watch everything downstream re-run.
        """
    )
    return


@app.cell
def _(mo):
    n = mo.ui.slider(1, 20, value=5, label="n")
    n
    return (n,)


@app.cell
def _(n):
    squares = [i * i for i in range(1, n.value + 1)]
    squares
    return


if __name__ == "__main__":
    app.run()
