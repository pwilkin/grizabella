"""QThread worker for executing Grizabella API client calls asynchronously."""

from typing import Any, Optional

from PySide6.QtCore import QObject, QThread, Signal, Slot


class ApiClientThread(QThread):
    """A QThread to prepare data for Grizabella API calls and request their execution
    on the main thread. It then handles the response.
    """

    # Signal to request an API call on the main thread
    # Carries: operation_name (str), args (tuple), kwargs (dict)
    apiRequestReady = Signal(str, tuple, dict)

    # Signals to communicate the final result/error back to the original caller
    result_ready = Signal(object)  # Emits the result of the API call
    error_occurred = Signal(str)   # Emits an error message string

    # finished signal is inherited from QThread

    def __init__(
        self,
        operation_name: str,
        *args: Any,
        parent: Optional[QObject] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(parent)
        self.operation_name = operation_name
        self.args = args
        self.kwargs = kwargs
        # Store a reference to self to be passed with apiRequestReady if needed
        # for the main thread to call back the correct handleApiResponse slot.
        # However, a direct connection from main_window to this instance's slot is better.

    def run(self) -> None:
        """Prepares data (if necessary) and emits a signal to request the API call
        on the main thread.
        """
        try:
            # In this new model, data preparation for the API call would happen here if CPU-intensive.
            # For now, we assume preparation is light and just pass through the request.
            self.apiRequestReady.emit(self.operation_name, self.args, self.kwargs)
        except Exception as e:
            # If an error occurs during preparation (before main thread call)
            self.error_occurred.emit(f"Error in worker thread before API call: {e}")
        finally:
            # The 'finished' signal will be emitted automatically by QThread when run() completes.
            # If run() is very short (just emitting a signal), this is fine.
            # If there was significant prep, ensure it's robust.
            pass # self.finished.emit() is implicitly handled by QThread

    @Slot(bool, object)
    def handleApiResponse(self, success: bool, result_or_error: Any) -> None:
        """Slot to receive the API call's result (or error) from the main thread.
        It then emits the appropriate signal (result_ready or error_occurred)
        to the original UI component that initiated the operation.
        """
        if success:
            self.result_ready.emit(result_or_error)
        elif isinstance(result_or_error, Exception):
            self.error_occurred.emit(f"API Error: {result_or_error}")
        else:
            self.error_occurred.emit(str(result_or_error))
        # self.finished.emit() should not be here, as run() has already finished.
        # The lifecycle of the thread object itself is managed by who created it.
        # If this thread instance is meant to be one-shot, it will be garbage collected
        # after its signals are processed, provided no strong references remain.
