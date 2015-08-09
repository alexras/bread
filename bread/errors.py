class BadConditionalCaseError(Exception):
    def __init__(self, case):
        super(BadConditionalCaseError, self).__init__(
            "No known conditional case '%s'" % (case))
