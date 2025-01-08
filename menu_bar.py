# menu_bar.py

class MenuBar:
    def __init__(self, main_window):
        """
        Initialize the MenuBar with a reference to the main window.

        :param main_window: The instance of the main application window.
        """
        self.main_window = main_window
        self.setup_menu_bar()

    def setup_menu_bar(self):
        self.main_window.menu_bar = self.main_window.menuBar()
        
        # File Menu
        self.main_window.file_menu = self.main_window.menu_bar.addMenu("File")
        
        # Save Action
        save_action = self.main_window.create_action(
            name="Save",
            shortcut="Ctrl+S",
            triggered=self.main_window.trigger_save_album_data
        )
        self.main_window.file_menu.addAction(save_action)
        
        # Save As Action
        save_as_action = self.main_window.create_action(
            name="Save As...",
            shortcut="Ctrl+Shift+S",
            triggered=self.main_window.trigger_save_as_album_data
        )
        self.main_window.file_menu.addAction(save_as_action)
        
        # Open Action
        open_action = self.main_window.create_action(
            name="Open",
            shortcut="Ctrl+O",
            triggered=self.main_window.trigger_load_album_data
        )
        self.main_window.file_menu.addAction(open_action)
        
        # Close File Action
        close_action = self.main_window.create_action(
            name="Close File",
            shortcut="Ctrl+W",
            triggered=self.main_window.close_album_data
        )
        self.main_window.file_menu.addAction(close_action)
        
        # Recent Files Submenu
        self.main_window.recent_files_menu = self.main_window.file_menu.addMenu("Recent Files")
        self.main_window.update_recent_files_menu()
        
        # Separator
        self.main_window.file_menu.addSeparator()
        
        # Submit via Telegram Action
        submit_action = self.main_window.create_action(
            name="Submit via Telegram",
            triggered=self.main_window.openSubmitDialog
        )
        self.main_window.file_menu.addAction(submit_action)
        
        # Add Album Manually Action
        manual_add_album_action = self.main_window.create_action(
            name="Add Album Manually",
            triggered=self.main_window.open_manual_add_album_dialog
        )
        self.main_window.file_menu.addAction(manual_add_album_action)
        
        # View Logs Action
        view_logs_action = self.main_window.create_action(
            name="View Logs",
            triggered=self.main_window.open_log_viewer
        )
        self.main_window.file_menu.addAction(view_logs_action)
        
        # Separator
        self.main_window.file_menu.addSeparator()
        
        # Import Config Action
        import_config_action = self.main_window.create_action(
            name="Import Config",
            triggered=self.main_window.import_config
        )
        self.main_window.file_menu.addAction(import_config_action)
        
        # Request Genres Action
        request_genres_action = self.main_window.create_action(
            name="Request Genres",
            shortcut="Ctrl+G",
            triggered=self.main_window.open_send_genre_dialog
        )
        self.main_window.file_menu.addAction(request_genres_action)
        
        # Find Action
        find_action = self.main_window.create_action(
            name="Find",
            shortcut="Ctrl+F",
            triggered=self.main_window.show_search_bar
        )
        self.main_window.file_menu.addAction(find_action)
        
        # Separator
        self.main_window.file_menu.addSeparator()
        
        # Quit Action
        quit_action = self.main_window.create_action(
            name="Quit",
            shortcut="Ctrl+Q",
            triggered=self.main_window.close_application
        )
        self.main_window.file_menu.addAction(quit_action)
        
        # Help Menu
        self.main_window.help_menu = self.main_window.menu_bar.addMenu("Help")
        help_action = self.main_window.create_action(
            name="Help",
            triggered=self.main_window.show_help
        )
        self.main_window.help_menu.addAction(help_action)
        
        # About Menu
        self.main_window.about_menu = self.main_window.menu_bar.addMenu("About")
        about_action = self.main_window.create_action(
            name="About SuShe",
            triggered=self.main_window.show_about_dialog
        )
        self.main_window.about_menu.addAction(about_action)