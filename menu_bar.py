# menu_bar.py

class MenuBar:
    def __init__(self, main_window):
        self.main_window = main_window
        self.setup_menu_bar()

    def setup_menu_bar(self):
        bar = self.main_window.menuBar()

        file_menu = bar.addMenu("File")
        
        open_action = self.main_window.create_action(
            "Open", "Ctrl+O", triggered=self.main_window.trigger_load_album_data
        )
        file_menu.addAction(open_action)

        save_action = self.main_window.create_action(
            "Save", "Ctrl+S", triggered=self.main_window.trigger_save_album_data
        )
        file_menu.addAction(save_action)

        save_as_action = self.main_window.create_action(
            "Save As...", "Ctrl+Shift+S", triggered=self.main_window.trigger_save_as_album_data
        )
        file_menu.addAction(save_as_action)

        export_list_action = self.main_window.create_action(
            "Export List", "Ctrl+Shift+E", triggered=self.main_window.export_album_data_html
        )
        file_menu.addAction(export_list_action)

        close_action = self.main_window.create_action(
            "Close File", "Ctrl+W", triggered=self.main_window.close_album_data
        )
        file_menu.addAction(close_action)

        self.main_window.recent_files_menu = file_menu.addMenu("Recent Files")
        self.main_window.update_recent_files_menu()

        file_menu.addSeparator()

        submit_action = self.main_window.create_action(
            "Submit via Telegram", triggered=self.main_window.openSubmitDialog
        )
        file_menu.addAction(submit_action)

        manual_add_album_action = self.main_window.create_action(
            "Add Album Manually", triggered=self.main_window.open_manual_add_album_dialog
        )
        file_menu.addAction(manual_add_album_action)

        view_logs_action = self.main_window.create_action(
            "View Logs", triggered=self.main_window.open_log_viewer
        )
        file_menu.addAction(view_logs_action)

        file_menu.addSeparator()

        import_config_action = self.main_window.create_action(
            "Import Config", triggered=self.main_window.import_config
        )
        file_menu.addAction(import_config_action)

        request_genres_action = self.main_window.create_action(
            "Request Genres", "Ctrl+G", triggered=self.main_window.open_send_genre_dialog
        )
        file_menu.addAction(request_genres_action)

        find_action = self.main_window.create_action(
            "Find", "Ctrl+F", triggered=self.main_window.show_search_bar
        )
        file_menu.addAction(find_action)

        file_menu.addSeparator()

        quit_action = self.main_window.create_action(
            "Quit", "Ctrl+Q", triggered=self.main_window.close_application
        )
        file_menu.addAction(quit_action)

        help_menu = bar.addMenu("Help")
        help_action = self.main_window.create_action(
            "Help", triggered=self.main_window.show_help
        )
        help_menu.addAction(help_action)

        about_menu = bar.addMenu("About")
        about_action = self.main_window.create_action(
            "About SuShe", triggered=self.main_window.show_about_dialog
        )
        about_menu.addAction(about_action)