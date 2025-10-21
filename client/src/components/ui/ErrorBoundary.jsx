import { Component } from "react";

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    // eslint-disable-next-line no-console
    console.error("Load Optimization render error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-6">
          <div className="alert alert-error">
            <span>
              Something went wrong while rendering this section.
              {this.state.error ? ` (${this.state.error.message})` : null}
            </span>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;


