import React from 'react';
export class ErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { hasError: false, error: null }; }
  static getDerivedStateFromError(error) { return { hasError: true, error }; }
  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary">
          <h2>頁面發生錯誤</h2>
          <p>{this.state.error?.message}</p>
          <button className="btn btn-primary" onClick={() => this.setState({ hasError: false, error: null })}>重試</button>
        </div>
      );
    }
    return this.props.children;
  }
}
