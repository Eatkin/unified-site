TMUX_SESSION_NAME=flask_server

start:
	@if tmux has-session -t $(TMUX_SESSION_NAME) 2>/dev/null; then \
		echo "Tmux session '$(TMUX_SESSION_NAME)' already exists."; \
		echo "Flask server might already be running."; \
	else \
		tmux new-session -d -s $(TMUX_SESSION_NAME) 'flask run'; \
		echo "Flask server started at http://127.0.0.1:5000"; \
	fi

stop:
	@if tmux has-session -t $(TMUX_SESSION_NAME) 2>/dev/null; then \
		tmux kill-session -t $(TMUX_SESSION_NAME); \
		echo "Flask server stopped."; \
	else \
		echo "No tmux session named '$(TMUX_SESSION_NAME)' found."; \
	fi

submit_build:
	gcloud builds submit --tag europe-west2-docker.pkg.dev/homepage-428615/homepage/homepage:latest
