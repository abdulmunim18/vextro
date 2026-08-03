export function getApiErrorMessage(
  error,
  fallbackMessage = "Something went wrong. Please try again.",
) {
  const responseDetail = error.response?.data?.detail;

  if (typeof responseDetail === "string") {
    return responseDetail;
  }

  if (
    responseDetail &&
    typeof responseDetail === "object" &&
    !Array.isArray(responseDetail) &&
    responseDetail.message
  ) {
    return responseDetail.message;
  }

  if (
    Array.isArray(responseDetail) &&
    responseDetail.length > 0
  ) {
    return responseDetail[0]?.msg || fallbackMessage;
  }

  if (error.code === "ECONNABORTED") {
    return "The server took too long to respond.";
  }

  if (!error.response) {
    return "Unable to connect to the VEXTRO backend.";
  }

  return fallbackMessage;
}