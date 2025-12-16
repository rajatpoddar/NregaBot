from tkinter import messagebox

class WorkflowManager:
    def __init__(self, app):
        self.app = app

    def _wait_and_execute(self, tab_name, action_callback):
        """Helper to wait for a tab to load before executing action."""
        if tab_name in self.app.tab_instances:
            # Thoda extra delay taaki UI render ho chuka ho
            self.app.after(200, action_callback)
        else:
            # Retry after 100ms
            self.app.after(100, lambda: self._wait_and_execute(tab_name, action_callback))

    def switch_to_if_edit_with_data(self, data):
        self.app.show_frame("IF Editor")
        def _action():
            self.app.tab_instances["IF Editor"].load_data_from_wc_gen(data)
            self.app.play_sound("success")
            messagebox.showinfo("Data Transferred", f"{len(data)} items transferred.")
        self._wait_and_execute("IF Editor", _action)

    def run_work_allocation_from_demand(self, panchayat_name, work_key):
        self.app.show_frame("Allocation")
        def _action():
            self.app.tab_instances["Allocation"].run_automation_from_demand(panchayat_name, work_key)
            self.app.play_sound("success")
            messagebox.showinfo("Handoff", "Starting Work Allocation...")
        self._wait_and_execute("Allocation", _action)

    def switch_to_msr_tab_with_data(self, workcodes, panchayat_name):
        self.app.show_frame("MR Payment")
        def _action():
            self.app.tab_instances["MR Payment"].load_data_from_mr_tracking(workcodes, panchayat_name)
            self.app.play_sound("success")
            messagebox.showinfo("Data Transferred", "Data sent to MR Payment.")
        self._wait_and_execute("MR Payment", _action)

    def switch_to_emb_entry_with_data(self, workcodes, panchayat_name):
        self.app.show_frame("eMB Entry")
        def _action():
            self.app.tab_instances["eMB Entry"].load_data_from_mr_tracking(workcodes, panchayat_name)
            self.app.play_sound("success")
            messagebox.showinfo("Data Transferred", "Data sent to eMB Entry.")
        self._wait_and_execute("eMB Entry", _action)

    def switch_to_mr_fill_with_data(self, workcodes, panchayat_name):
        self.app.show_frame("MR Fill")
        def _action():
            self.app.tab_instances["MR Fill"].load_data_from_dashboard(workcodes, panchayat_name)
            self.app.play_sound("success")
            messagebox.showinfo("Data Transferred", "Data sent to MR Fill.")
        self._wait_and_execute("MR Fill", _action)

    def switch_to_mr_tracking_for_abps(self):
        self.app.show_frame("MR Tracking")
        def _action():
            self.app.tab_instances["MR Tracking"].set_for_abps_check()
            self.app.play_sound("success")
            messagebox.showinfo("Action Required", "Fill details to check ABPS Labour")
        self._wait_and_execute("MR Tracking", _action)

    def switch_to_duplicate_mr_with_data(self, workcodes, panchayat_name):
        self.app.show_frame("Duplicate MR Print")
        def _action():
            self.app.tab_instances["Duplicate MR Print"].load_data_from_report(workcodes, panchayat_name)
            self.app.play_sound("success")
            messagebox.showinfo("Data Transferred", "Data sent to Duplicate MR.")
        self._wait_and_execute("Duplicate MR Print", _action)

    def switch_to_zero_mr_tab_with_data(self, data_list):
        self.app.show_frame("Zero Mr")
        def _action():
            self.app.tab_instances["Zero Mr"].load_data_from_mr_tracking(data_list)
            self.app.play_sound("success")
            messagebox.showinfo("Data Transferred", "Data sent to Zero MR.")
        self._wait_and_execute("Zero Mr", _action)

    def send_wagelist_data_and_switch_tab(self, start, end):
        self.app.show_frame("Send Wagelist")
        def _action():
            self.app.tab_instances["Send Wagelist"].populate_wagelist_data(start, end)
        self._wait_and_execute("Send Wagelist", _action)