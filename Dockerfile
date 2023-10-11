# Use the official Swift image as the base
FROM swift:5.7

# Set the working directory in the container
WORKDIR /app

# Copy the local package list to the container's workspace.
COPY . ./ 

# Compile the application.
RUN swift build --configuration release

# Run the bot when the container launches.
CMD ["swift", "run", "--configuration", "release"]
